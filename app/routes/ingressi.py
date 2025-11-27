# app/routes/ingressi.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.utils.decorators import require_cliente, require_admin, require_staff
from app.routes.log_attivita import log_action
from app.utils.events import get_evento_operativo
from app.utils.helpers import get_current_staff_id, cliente_has_ingresso

from app.models.clienti import Cliente
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.prenotazioni import Prenotazione
from app.models.staff import Staff
from app.routes.fedelta import award_on_ingresso

ingressi_bp = Blueprint("ingressi", __name__, url_prefix="/ingressi")

TIPI = ("lista", "tavolo", "omaggio", "prevendita")


# ---------------------------
# Helpers specifici ingressi
# ---------------------------
def _capienza_counts(db, evento_id):
    """Conta il numero totale di ingressi per un evento."""
    return db.query(func.count(Ingresso.id_ingresso)).filter(
        Ingresso.evento_id == evento_id
    ).scalar() or 0

def _active_prenotazione(db, cliente_id, evento_id):
    """Trova la prenotazione attiva di un cliente per un evento."""
    return db.query(Prenotazione).filter(
        Prenotazione.cliente_id == cliente_id,
        Prenotazione.evento_id == evento_id,
        Prenotazione.stato == "attiva"
    ).first()


# ============================================
# 👤 CLIENTE — Storico ingressi
# ============================================
@ingressi_bp.route("/mie", methods=["GET"])
@require_cliente
def mie():
    from app.utils.helpers import get_current_cliente_id
    db = SessionLocal()
    try:
        cid = get_current_cliente_id()
        rows = db.query(Ingresso).join(Evento, Evento.id_evento == Ingresso.evento_id) \
            .filter(Ingresso.cliente_id == cid) \
            .order_by(Ingresso.orario_ingresso.desc()) \
            .all()
        return render_template("clienti/ingressi_list.html", ingressi=rows)
    finally:
        db.close()


# ============================================
# 🧑‍🍳 STAFF — Scan QR (evento attivo in sessione)
# ============================================
@ingressi_bp.route("/staff/scan", methods=["GET", "POST"])
@require_staff
def staff_scan():
    db = SessionLocal()
    try:
        e = get_evento_operativo(db)
        if not e:
            flash("Evento chiuso: non è possibile registrare nuovi ingressi.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        if e.stato_pubblico == "chiuso" or not e.is_staff_operativo:
            flash("Evento chiuso: non è possibile registrare nuovi ingressi.", "warning")
            return redirect(url_for("eventi.staff_select_event"))

        if request.method == "POST":
            qr = (request.form.get("qr") or "").strip()
            if not qr:
                flash("QR mancante.", "danger")
                return redirect(url_for("ingressi.staff_scan"))

            cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
            if not cli:
                flash("QR non valido o cliente non trovato.", "danger")
                return redirect(url_for("ingressi.staff_scan"))

            # No doppio ingresso
            if cliente_has_ingresso(db, cli.id_cliente, e.id_evento):
                flash("Cliente già entrato per questo evento.", "warning")
                return redirect(url_for("ingressi.staff_scan"))

            # Capienza: blocco con override esplicito
            tot = _capienza_counts(db, e.id_evento)
            if e.capienza_max is not None and tot >= e.capienza_max and request.form.get("override_capienza") != "1":
                # Mostra pagina di conferma override
                return render_template(
                    "staff/ingressi_confirm_override.html",
                    evento=e,
                    cliente=cli,
                    tot_ingressi=tot,
                    capienza=e.capienza_max,
                    qr=qr
                )

            # Se ha prenotazione attiva: usa quel tipo e marca 'usata'
            pren = _active_prenotazione(db, cli.id_cliente, e.id_evento)
            if pren:
                tipo_ingresso = pren.tipo
                # Verifica approvazione per prenotazioni tavolo
                if pren.tipo == "tavolo" and pren.stato_approvazione_tavolo != "approvata":
                    flash("La prenotazione tavolo non è stata ancora approvata. Impossibile registrare l'ingresso.", "warning")
                    return redirect(url_for("ingressi.staff_scan"))
            else:
                # Nessuna prenotazione -> distinguiamo automaticamente come 'lista'
                tipo_ingresso = "lista"

            ingresso = Ingresso(
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                prenotazione_id=pren.id_prenotazione if pren else None,
                staff_id=get_current_staff_id(),
                tipo_ingresso=tipo_ingresso,
                note=None
            )
            db.add(ingresso)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                flash("Cliente già entrato per questo evento.", "warning")
                return redirect(url_for("ingressi.staff_scan"))

            # Marca prenotazione come usata se presente
            if pren:
                pren.stato = "usata"
                log_action(
                    db,
                    tabella="prenotazioni",
                    record_id=pren.id_prenotazione,
                    staff_id=get_current_staff_id(),
                    azione="prenotazione_usata",
                    note=f"evento_id={e.id_evento}"
                )

            if e.capienza_max is not None and tot >= e.capienza_max and request.form.get("override_capienza") == "1":
                # Logga override capienza
                note = f"Capienza superata {tot}/{e.capienza_max}, ingresso forzato"
                log_action(db, tabella="ingressi", record_id=ingresso.id_ingresso, staff_id=get_current_staff_id(), azione="override_capienza", note=note)
            log_action(
                db,
                tabella="ingressi",
                record_id=ingresso.id_ingresso,
                staff_id=get_current_staff_id(),
                azione="ingresso_automatico",
                note=f"evento_id={e.id_evento}"
            )
            db.commit()
            award_on_ingresso(
                db,
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                has_prenotazione=pren is not None
            )
            if pren:
                flash("Prenotazione trovata e convalidata, ingresso registrato.", "success")
            else:
                flash("Cliente non prenotato, ingresso registrato come lista.", "info")
            return redirect(url_for("ingressi.staff_esito", ingresso_id=ingresso.id_ingresso))

        # GET
        ingressi_totali = _capienza_counts(db, e.id_evento)
        residua = (e.capienza_max - ingressi_totali) if e.capienza_max is not None else None
        return render_template(
            "staff/ingressi_scan_qr_evento.html",
            evento=e,
            ingressi_totali=ingressi_totali,
            residua=residua
        )
    finally:
        db.close()


@ingressi_bp.route("/staff/prenotati-count", methods=["GET"])
@require_staff
def staff_prenotati_count():
    """
    Ritorna il numero di prenotazioni ancora 'attive' (non usate) per l'evento operativo.
    Utile per il contatore real-time degli ingressi.
    """
    db = SessionLocal()
    try:
        e = get_evento_operativo(db)
        if not e:
            return jsonify({"ok": False, "reason": "no_event"}), 409

        # Conta prenotazioni attive (stato='attiva')
        prenotati_count = db.query(func.count(Prenotazione.id_prenotazione)).filter(
            Prenotazione.evento_id == e.id_evento,
            Prenotazione.stato == "attiva"
        ).scalar() or 0

        # Conta ingressi totali
        ingressi_count = _capienza_counts(db, e.id_evento)

        return jsonify({
            "ok": True,
            "prenotati_mancanti": prenotati_count,
            "ingressi_totali": ingressi_count,
            "capienza": e.capienza_max
        }), 200
    finally:
        db.close()


@ingressi_bp.route("/staff/scan/check", methods=["POST"])
@require_staff
def staff_scan_check():
    """
    Endpoint JSON di pre-verifica:
    - verifica che esista un evento attivo
    - verifica che il QR corrisponda a un cliente
    - verifica che non sia già stato registrato l'ingresso per l'evento
    Ritorna:
      { ok: true }                            -> consentire submit
      { ok: false, reason: 'not_found' }      -> QR non valido
      { ok: false, reason: 'already' }        -> già entrato
      { ok: false, reason: 'no_event' }       -> nessun evento attivo
    """
    db = SessionLocal()
    try:
        e = get_evento_operativo(db)
        if not e:
            return jsonify({"ok": False, "reason": "no_event"}), 200
        if e.stato_pubblico == "chiuso" or not e.is_staff_operativo:
            return jsonify({"ok": False, "reason": "event_closed"}), 200
        data = request.get_json(silent=True) or {}
        qr = (data.get("qr") or request.form.get("qr") or "").strip()
        if not qr:
            return jsonify({"ok": False, "reason": "not_found"}), 200
        cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
        if not cli:
            return jsonify({"ok": False, "reason": "not_found"}), 200
        if cliente_has_ingresso(db, cli.id_cliente, e.id_evento):
            return jsonify({"ok": False, "reason": "already"}), 200
        return jsonify({"ok": True}), 200
    finally:
        db.close()


@ingressi_bp.route("/staff/scan/preview", methods=["POST"])
@require_staff
def staff_scan_preview():
    """
    Ritorna i dettagli del cliente per conferma prima del check-in.
    Input JSON: { qr: "..." }
    Output:
      { ok: true,
        cliente: { nome, cognome, data_nascita, citta, id },
        already: bool
      }
      Oppure { ok: false, reason: 'no_event'|'not_found' }
    """
    db = SessionLocal()
    try:
        e = get_evento_operativo(db)
        if not e:
            return jsonify({"ok": False, "reason": "no_event"}), 200
        if e.stato_pubblico == "chiuso" or not e.is_staff_operativo:
            return jsonify({"ok": False, "reason": "event_closed"}), 200
        data = request.get_json(silent=True) or {}
        qr = (data.get("qr") or "").strip()
        if not qr:
            return jsonify({"ok": False, "reason": "not_found"}), 200
        cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
        if not cli:
            return jsonify({"ok": False, "reason": "not_found"}), 200
        already = cliente_has_ingresso(db, cli.id_cliente, e.id_evento)
        cliente_payload = {
            "id": cli.id_cliente,
            "nome": cli.nome,
            "cognome": cli.cognome,
            "data_nascita": str(cli.data_nascita) if getattr(cli, "data_nascita", None) else None,
            "citta": getattr(cli, "citta", None)
        }
        return jsonify({"ok": True, "cliente": cliente_payload, "already": already}), 200
    finally:
        db.close()

@ingressi_bp.route("/staff/esito/<int:ingresso_id>", methods=["GET"])
@require_staff
def staff_esito(ingresso_id):
    db = SessionLocal()
    try:
        ing = db.query(Ingresso).get(ingresso_id)
        if not ing:
            flash("Ingresso non trovato.", "danger")
            return redirect(url_for("ingressi.staff_scan"))
        cli = db.query(Cliente).get(ing.cliente_id)
        e = db.query(Evento).get(ing.evento_id)
        return render_template("staff/ingressi_esito.html", ingresso=ing, cliente=cli, evento=e)
    finally:
        db.close()


# ============================================
# 👑 ADMIN — Liste/Filtri, CRUD manuale, Undo, Analytics
# ============================================
@ingressi_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Parametri paginazione
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 10), 200)
        
        # Filtri
        evento_id = request.args.get("evento_id", type=int)
        tipo = request.args.get("tipo_ingresso")
        staff_id = request.args.get("staff_id", type=int)
        dal = request.args.get("dal")  # YYYY-MM-DD
        al = request.args.get("al")    # YYYY-MM-DD

        q = db.query(Ingresso, Cliente, Evento).join(Cliente, Cliente.id_cliente == Ingresso.cliente_id) \
                                               .join(Evento, Evento.id_evento == Ingresso.evento_id)

        if evento_id:
            q = q.filter(Ingresso.evento_id == evento_id)
        if tipo in TIPI:
            q = q.filter(Ingresso.tipo_ingresso == tipo)
        if staff_id:
            q = q.filter(Ingresso.staff_id == staff_id)
        if dal:
            try:
                d = datetime.strptime(dal, "%Y-%m-%d")
                q = q.filter(Ingresso.orario_ingresso >= d)
            except ValueError:
                pass
        if al:
            try:
                d2 = datetime.strptime(al, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(Ingresso.orario_ingresso < d2)
            except ValueError:
                pass

        # Conta totale
        total = q.count()
        
        # Applica paginazione
        rows = q.order_by(Ingresso.orario_ingresso.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()
        
        # Calcola pagine
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()
        
        # Conteggio prenotazioni tavolo in attesa
        from app.models.prenotazioni import Prenotazione
        prenotazioni_tavolo_attesa_count = db.query(func.count(Prenotazione.id_prenotazione))\
            .filter(
                Prenotazione.tipo == "tavolo",
                Prenotazione.stato_approvazione_tavolo == "in_attesa"
            ).scalar() or 0
        
        return render_template("admin/ingressi_list.html", 
                             rows=rows, 
                             eventi=eventi, 
                             staff_list=staff_list,
                             filtro={"evento_id": evento_id, "tipo": tipo, "staff_id": staff_id, "dal": dal, "al": al},
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages,
                             pages_list=pages_list,
                             prenotazioni_tavolo_attesa_count=prenotazioni_tavolo_attesa_count)
    finally:
        db.close()


@ingressi_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        clienti = db.query(Cliente).order_by(Cliente.cognome.asc(), Cliente.nome.asc()).all()
        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id", type=int)
            evento_id = request.form.get("evento_id", type=int)
            tipo = request.form.get("tipo_ingresso")
            note = (request.form.get("note") or "").strip()
            staff_id = request.form.get("staff_id", type=int)

            if tipo not in TIPI:
                flash("Tipo ingresso non valido.", "danger")
                return redirect(url_for("ingressi.admin_new"))

            # No doppio ingresso
            if cliente_has_ingresso(db, cliente_id, evento_id):
                flash("Cliente già entrato per questo evento.", "warning")
                return redirect(url_for("ingressi.admin_list"))

            # Collega prenotazione attiva se coerente (lista/tavolo/prevendita)
            pren = _active_prenotazione(db, cliente_id, evento_id)
            pren_id = pren.id_prenotazione if pren and pren.tipo == tipo else None

            ing = Ingresso(
                cliente_id=cliente_id,
                evento_id=evento_id,
                prenotazione_id=pren_id,
                staff_id=staff_id,
                tipo_ingresso=tipo,
                note=note or None
            )
            db.add(ing)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                flash("Cliente già entrato per questo evento.", "warning")
                return redirect(url_for("ingressi.admin_list"))
            if pren_id:
                pren.stato = "usata"
                log_action(
                    db,
                    tabella="prenotazioni",
                    record_id=pren_id,
                    staff_id=staff_id,
                    azione="prenotazione_usata",
                    note=f"evento_id={evento_id}"
                )
            log_action(
                db,
                tabella="ingressi",
                record_id=ing.id_ingresso,
                staff_id=staff_id,
                azione="ingresso_automatico",
                note=f"evento_id={evento_id}"
            )
            db.commit()
            award_on_ingresso(
                db,
                cliente_id=cliente_id,
                evento_id=evento_id,
                has_prenotazione=pren_id is not None
            )
            if pren_id:
                flash("Prenotazione trovata e convalidata, ingresso registrato.", "success")
            else:
                flash("Ingresso registrato correttamente.", "success")
            return redirect(url_for("ingressi.admin_ingresso_detail", ingresso_id=ing.id_ingresso))

        return render_template("admin/ingressi_form.html", e=None, eventi=eventi, clienti=clienti, staff_list=staff_list)
    finally:
        db.close()


@ingressi_bp.route("/admin/<int:ingresso_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(ingresso_id):
    db = SessionLocal()
    try:
        ing = db.query(Ingresso).get(ingresso_id)
        if not ing:
            flash("Ingresso non trovato.", "danger")
            return redirect(url_for("ingressi.admin_list"))

        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()

        if request.method == "POST":
            tipo = request.form.get("tipo_ingresso")
            note = (request.form.get("note") or "").strip()
            staff_id = request.form.get("staff_id", type=int)

            if tipo not in TIPI:
                flash("Tipo ingresso non valido.", "danger")
                return redirect(url_for("ingressi.admin_edit", ingresso_id=ingresso_id))

            ing.tipo_ingresso = tipo
            ing.note = note or None
            ing.staff_id = staff_id
            db.flush()
            log_action(db, tabella="ingressi", record_id=ing.id_ingresso, staff_id=staff_id, azione="update")
            db.commit()
            flash("Ingresso aggiornato.", "success")
            return redirect(url_for("ingressi.admin_ingresso_detail", ingresso_id=ingresso_id))

        return render_template("admin/ingressi_form.html", e=ing, eventi=[], clienti=[], staff_list=staff_list)
    finally:
        db.close()


@ingressi_bp.route("/admin/<int:ingresso_id>", methods=["GET"])
@require_admin
def admin_ingresso_detail(ingresso_id):
    db = SessionLocal()
    try:
        ing = db.query(Ingresso).get(ingresso_id)
        if not ing:
            flash("Ingresso non trovato.", "danger")
            return redirect(url_for("ingressi.admin_list"))
        
        # Carica relazioni
        cliente = db.query(Cliente).get(ing.cliente_id)
        evento = db.query(Evento).get(ing.evento_id)
        staff = None
        if ing.staff_id:
            staff = db.query(Staff).get(ing.staff_id)
        
        # Carica prenotazione collegata se presente
        prenotazione = None
        if ing.prenotazione_id:
            prenotazione = db.query(Prenotazione).get(ing.prenotazione_id)
        
        return render_template("admin/ingresso_detail.html",
                             ingresso=ing,
                             cliente=cliente,
                             evento=evento,
                             staff=staff,
                             prenotazione=prenotazione)
    finally:
        db.close()


@ingressi_bp.route("/admin/<int:ingresso_id>/delete", methods=["POST"])
@require_admin
def admin_delete(ingresso_id):
    db = SessionLocal()
    try:
        ing = db.query(Ingresso).get(ingresso_id)
        if ing:
            # Undo prenotazione: se collegata e marcata 'usata', torna 'attiva'
            if ing.prenotazione_id:
                pren = db.query(Prenotazione).get(ing.prenotazione_id)
                if pren and pren.stato == "usata":
                    pren.stato = "attiva"
            db.delete(ing)
            db.flush()
            log_action(db, tabella="ingressi", record_id=ingresso_id, staff_id=None, azione="delete")
            db.commit()
            flash("Check-in annullato (ingresso eliminato).", "warning")
        return redirect(url_for("ingressi.admin_list"))
    finally:
        db.close()


@ingressi_bp.route("/admin/<int:evento_id>/analytics", methods=["GET"])
@require_admin
def admin_analytics(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("ingressi.admin_list"))

        # Totali e breakdown
        tot = db.query(func.count(Ingresso.id_ingresso)).filter(Ingresso.evento_id == evento_id).scalar() or 0
        per_tipo = dict(db.query(Ingresso.tipo_ingresso, func.count(Ingresso.id_ingresso))
                          .filter(Ingresso.evento_id == evento_id)
                          .group_by(Ingresso.tipo_ingresso).all())
        per_staff = dict(db.query(Ingresso.staff_id, func.count(Ingresso.id_ingresso))
                           .filter(Ingresso.evento_id == evento_id)
                           .group_by(Ingresso.staff_id).all())

        # Ritmo ultimi 15 minuti
        now = datetime.now()
        last15 = db.query(func.count(Ingresso.id_ingresso)).filter(
            Ingresso.evento_id == evento_id,
            Ingresso.orario_ingresso >= (now - timedelta(minutes=15))
        ).scalar() or 0

        return render_template("admin/ingressi_analytics.html",
                               e=e, tot=tot, per_tipo=per_tipo, per_staff=per_staff, last15=last15)
    finally:
        db.close()