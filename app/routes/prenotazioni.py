# app/routes/prenotazioni.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy import func, and_
from datetime import datetime, date, time
from collections import defaultdict
from app.database import SessionLocal
from app.models.prenotazioni import Prenotazione
from app.models.eventi import Evento
from app.models.clienti import Cliente
from app.models.consumi import Consumo
from app.models.feedback import Feedback
from app.models.fedeltà import Fedelta
from app.models.ingressi import Ingresso
from app.utils.decorators import require_cliente, require_admin, require_staff
from app.routes.fedelta import award_on_no_show, PUNTI_NO_SHOW
from app.utils.limiter import limiter

prenotazioni_bp = Blueprint("prenotazioni", __name__, url_prefix="/prenotazioni")

TIPI_CONSENTITI_CLIENTE = ("lista", "tavolo")
STATI = ("attiva", "no-show", "usata", "cancellata")


# ---------------------------
# Helpers (usano modulo centralizzato)
# ---------------------------
from app.utils.helpers import get_current_cliente as _get_current_cliente

def _has_active_for_event(db, cliente_id, evento_id):
    return db.query(Prenotazione).filter(
        Prenotazione.cliente_id == cliente_id,
        Prenotazione.evento_id == evento_id,
        Prenotazione.stato == "attiva"
    ).first() is not None

def _cliente_can_cancel(pren, evento):
    # Cancellabile fino al giorno stesso alle 18:00
    if not evento or not isinstance(evento.data_evento, date):
        return False
    cutoff = datetime.combine(evento.data_evento, time(18, 0))
    now = datetime.now()
    return pren.stato == "attiva" and now <= cutoff


# ============================================
# 👤 CLIENTE
# ============================================

# Crea prenotazione (da dettaglio evento)
@prenotazioni_bp.route("/nuova", methods=["GET", "POST"])
@require_cliente
@limiter.limit("10 per minute", key_func=lambda: session.get("cliente_id") or request.remote_addr)
def nuova():
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int) or request.form.get("evento_id", type=int)
        tipo_param = request.args.get("tipo")  # Parametro per tipo predefinito
        e = db.query(Evento).get(evento_id) if evento_id else None
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.lista_pubblica"))
        if e.stato_pubblico not in ("programmato", "attivo"):
            flash("Evento non disponibile per prenotazioni.", "warning")
            return redirect(url_for("eventi.dettaglio_pubblico", evento_id=e.id_evento))

        if request.method == "POST":
            cli = _get_current_cliente(db)
            if not cli:
                abort(401)

            # Regola: una sola prenotazione attiva per evento per cliente
            if _has_active_for_event(db, cli.id_cliente, e.id_evento):
                flash("Hai già una prenotazione attiva per questo evento.", "warning")
                return redirect(url_for("prenotazioni.mie"))

            tipo = request.form.get("tipo") or tipo_param
            if tipo not in TIPI_CONSENTITI_CLIENTE:
                flash("Tipo prenotazione non valido.", "danger")
                return redirect(url_for("prenotazioni.nuova", evento_id=e.id_evento))

            num_persone = request.form.get("num_persone", type=int)
            note = (request.form.get("note") or "").strip()
            orario_previsto = request.form.get("orario_previsto")  # opzionale (non usiamo prevendita)

            # Vincoli: tavolo -> solo nome tavolo obbligatorio (num_persone calcolato dal sistema)
            if tipo == "tavolo":
                if not note:
                    flash("Per il tavolo è obbligatorio indicare il nome del tavolo.", "danger")
                    return redirect(url_for("prenotazioni.nuova", evento_id=e.id_evento, tipo="tavolo"))

            pren = Prenotazione(
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                tipo=tipo,
                num_persone=None,  # Non più obbligatorio, calcolato dal sistema admin
                orario_previsto=orario_previsto or None,
                note=note or None,
                stato="attiva"
            )
            db.add(pren)
            db.commit()
            flash("Prenotazione creata correttamente.", "success")
            return redirect(url_for("prenotazioni.mie"))

        # GET
        tipo_default = tipo_param if tipo_param in TIPI_CONSENTITI_CLIENTE else None
        return render_template("clienti/prenotazioni_new.html", e=e, TIPI=TIPI_CONSENTITI_CLIENTE, tipo_default=tipo_default)
    finally:
        db.close()


# Crea prenotazione tavolo (flusso dedicato)
@prenotazioni_bp.route("/nuova-tavolo", methods=["GET", "POST"])
@require_cliente
def nuova_tavolo():
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int) or request.form.get("evento_id", type=int)
        e = db.query(Evento).get(evento_id) if evento_id else None
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.lista_pubblica"))
        if e.stato_pubblico not in ("programmato", "attivo"):
            flash("Evento non disponibile per prenotazioni.", "warning")
            return redirect(url_for("eventi.dettaglio_pubblico", evento_id=e.id_evento))

        if request.method == "POST":
            cli = _get_current_cliente(db)
            if not cli:
                abort(401)

            # Regola: una sola prenotazione attiva per evento per cliente
            if _has_active_for_event(db, cli.id_cliente, e.id_evento):
                flash("Hai già una prenotazione attiva per questo evento.", "warning")
                return redirect(url_for("prenotazioni.mie"))

            note = (request.form.get("note") or "").strip()
            if not note:
                flash("È obbligatorio indicare il nome del tavolo.", "danger")
                return redirect(url_for("prenotazioni.nuova_tavolo", evento_id=e.id_evento))

            pren = Prenotazione(
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                tipo="tavolo",
                num_persone=None,  # Calcolato dal sistema admin
                orario_previsto=None,
                note=note,
                stato="attiva"
            )
            db.add(pren)
            db.commit()
            flash("Prenotazione tavolo creata correttamente.", "success")
            return redirect(url_for("prenotazioni.mie"))

        # GET
        return render_template("clienti/prenotazioni_new_tavolo.html", e=e)
    finally:
        db.close()


# Lista mie prenotazioni (future + passate)
@prenotazioni_bp.route("/mie", methods=["GET"])
@require_cliente
def mie():
    from app.utils.workflow import get_workflow_state, processa_no_show_automatico, verifica_e_aggiorna_prenotazione_cliente
    from sqlalchemy.orm import joinedload
    db = SessionLocal()
    try:
        cli = _get_current_cliente(db)
        if not cli:
            abort(401)

        # ⚡ VERIFICA AUTOMATICA NO-SHOW: Processa tutte le prenotazioni del cliente che necessitano aggiornamento
        processa_no_show_automatico(db, cliente_id=cli.id_cliente)

        # Query ottimizzata con eager loading per evento
        pren = db.query(Prenotazione)\
            .options(joinedload(Prenotazione.evento))\
            .filter(
                Prenotazione.cliente_id == cli.id_cliente,
                Prenotazione.stato != "cancellata"
            )\
            .join(Evento, Prenotazione.evento_id == Evento.id_evento)\
            .order_by(Evento.data_evento.desc(), Prenotazione.id_prenotazione.desc())\
            .all()
        show_all = request.args.get("show_all")
        show_all_usate = (show_all == "usate")

        oggi = date.today()
        
        # Batch load ingressi e feedback del cliente (già ottimizzato)
        ingressi_map = {
            ing.evento_id: ing for ing in db.query(Ingresso)
            .filter(Ingresso.cliente_id == cli.id_cliente)
            .all()
        }

        feedbacks = {
            fb.evento_id: fb for fb in db.query(Feedback)
            .filter(Feedback.cliente_id == cli.id_cliente)
            .all()
        }

        # Separa prenotazioni per stato (dopo verifica automatica)
        pren_attive_future = []
        pren_usate = []
        pren_no_show = []
        
        for p in pren:
            # Verifica finale per sicurezza (doppio controllo)
            stato_finale = verifica_e_aggiorna_prenotazione_cliente(db, cli.id_cliente, p)
            
            if stato_finale == "attiva":
                if p.evento.data_evento >= oggi:
                    # Evento futuro: può ancora essere cancellata
                    pren_attive_future.append(p)
                else:
                    # Evento passato ma ancora attiva (edge case): verifica manuale
                    if p.evento_id in ingressi_map:
                        p.stato = "usata"
                        db.commit()
                        pren_usate.append((p, feedbacks.get(p.evento_id)))
                    else:
                        # Dovrebbe essere già no-show, ma per sicurezza
                        p.stato = "no-show"
                        db.commit()
                        pren_no_show.append(p)
            elif stato_finale == "usata":
                pren_usate.append((p, feedbacks.get(p.evento_id)))
            elif stato_finale == "no-show":
                pren_no_show.append(p)

        punti_per_no_show = abs(PUNTI_NO_SHOW)
        punti_persi = punti_per_no_show * len(pren_no_show)

        fedelta_map = defaultdict(int)
        for mov in db.query(Fedelta).filter(Fedelta.cliente_id == cli.id_cliente).all():
            if mov.evento_id:
                fedelta_map[mov.evento_id] += mov.punti or 0

        # Workflow state map per visualizzare lo stato completo
        workflow_map = {}
        for p in pren:
            workflow_map[p.id_prenotazione] = get_workflow_state(db, cli.id_cliente, p.evento_id)

        return render_template(
            "clienti/prenotazioni_list.html",
            prenotazioni_attive=pren_attive_future,
            prenotazioni_usate=pren_usate,
            prenotazioni_no_show=pren_no_show,
            punti_per_no_show=punti_per_no_show,
            punti_persi_no_show=punti_persi,
            punti_evento=fedelta_map,
            workflow_map=workflow_map,
            show_all_usate=show_all_usate,
            oggi=oggi
        )
    finally:
        db.close()


@prenotazioni_bp.route("/mie/<int:pren_id>", methods=["GET"])
@require_cliente
def mia_prenotazione_detail(pren_id):
    from app.utils.workflow import get_workflow_state
    db = SessionLocal()
    try:
        cli = _get_current_cliente(db)
        if not cli:
            abort(401)
        pren = db.query(Prenotazione).get(pren_id)
        if not pren or pren.cliente_id != cli.id_cliente:
            abort(404)
        
        # Mostra dettagli solo se la prenotazione è stata usata (= cliente è entrato)
        if pren.stato != "usata":
            flash("I dettagli consumo e feedback sono disponibili solo dopo aver usufruito della prenotazione.", "info")
            return redirect(url_for("prenotazioni.mie"))

        consumi = (
            db.query(Consumo)
            .filter(
                Consumo.cliente_id == cli.id_cliente,
                Consumo.evento_id == pren.evento_id
            )
            .order_by(Consumo.data_consumo.asc())
            .all()
        )

        feedback_esistente = db.query(Feedback).filter(
            Feedback.cliente_id == cli.id_cliente,
            Feedback.evento_id == pren.evento_id
        ).first()

        # Workflow state per mostrare il progresso
        workflow_state = get_workflow_state(db, cli.id_cliente, pren.evento_id)

        return render_template(
            "clienti/prenotazione_detail.html",
            prenotazione=pren,
            consumi=consumi,
            feedback_esistente=feedback_esistente,
            workflow_state=workflow_state
        )
    finally:
        db.close()


# Cancella prenotazione (entro le 18:00 del giorno dell'evento)
@prenotazioni_bp.route("/<int:pren_id>/cancella", methods=["POST"])
@require_cliente
def cancella_mia(pren_id):
    db = SessionLocal()
    try:
        cli = _get_current_cliente(db)
        pren = db.query(Prenotazione).get(pren_id)
        if not pren or pren.cliente_id != cli.id_cliente:
            abort(404)
        e = db.query(Evento).get(pren.evento_id)

        if not _cliente_can_cancel(pren, e):
            flash("Non è più possibile cancellare questa prenotazione.", "warning")
            return redirect(url_for("prenotazioni.mie"))

        pren.stato = "cancellata"
        db.commit()
        flash("Prenotazione cancellata.", "success")
        return redirect(url_for("prenotazioni.mie"))
    finally:
        db.close()


# ============================================
# 🧑‍🍳 STAFF (solo visualizzazione prenotati per evento)
# ============================================
@prenotazioni_bp.route("/staff/evento/<int:evento_id>", methods=["GET"])
@require_staff
def staff_lista_evento(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.staff_select_event"))

        pren = db.query(Prenotazione).join(Cliente, Cliente.id_cliente == Prenotazione.cliente_id) \
            .filter(Prenotazione.evento_id == evento_id) \
            .order_by(Prenotazione.tipo.asc(), Cliente.cognome.asc(), Cliente.nome.asc()) \
            .all()

        return render_template("staff/prenotazioni_evento.html", e=e, prenotazioni=pren)
    finally:
        db.close()


# ============================================
# 👑 ADMIN — Hub Operativo
# ============================================
@prenotazioni_bp.route("/admin/hub", methods=["GET"])
@require_admin
def admin_hub():
    """Hub centrale per la gestione operativa: prenotazioni, ingressi, consumi"""
    from app.models.ingressi import Ingresso
    from app.models.consumi import Consumo
    from app.utils.events import get_evento_operativo
    
    db = SessionLocal()
    try:
        # Evento operativo
        evento_operativo = get_evento_operativo(db)
        
        # Statistiche generali
        tot_prenotazioni_attive = db.query(func.count(Prenotazione.id_prenotazione))\
            .filter(Prenotazione.stato == "attiva").scalar() or 0
        tot_prenotazioni_oggi = 0
        tot_ingressi_oggi = 0
        tot_consumi_oggi = 0
        
        if evento_operativo:
            eid = evento_operativo.id_evento
            tot_prenotazioni_oggi = db.query(func.count(Prenotazione.id_prenotazione))\
                .filter(Prenotazione.evento_id == eid).scalar() or 0
            tot_ingressi_oggi = db.query(func.count(Ingresso.id_ingresso))\
                .filter(Ingresso.evento_id == eid).scalar() or 0
            tot_consumi_oggi = db.query(func.coalesce(func.sum(Consumo.importo), 0))\
                .filter(Consumo.evento_id == eid).scalar() or 0
        
        # Ultimi eventi per filtro rapido
        eventi_recenti = db.query(Evento).order_by(Evento.data_evento.desc()).limit(10).all()
        
        return render_template("admin/operativo_hub.html",
                             evento_operativo=evento_operativo,
                             tot_prenotazioni_attive=tot_prenotazioni_attive,
                             tot_prenotazioni_oggi=tot_prenotazioni_oggi,
                             tot_ingressi_oggi=tot_ingressi_oggi,
                             tot_consumi_oggi=float(tot_consumi_oggi),
                             eventi_recenti=eventi_recenti)
    finally:
        db.close()


# ============================================
# 👑 ADMIN — CRUD + regole + analytics
# ============================================
@prenotazioni_bp.route("/admin", methods=["GET"])
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
        tipo = request.args.get("tipo")
        stato = request.args.get("stato")

        q = db.query(Prenotazione, Cliente, Evento) \
              .join(Cliente, Cliente.id_cliente == Prenotazione.cliente_id) \
              .join(Evento, Evento.id_evento == Prenotazione.evento_id)

        if evento_id:
            q = q.filter(Prenotazione.evento_id == evento_id)
        if tipo in ("lista", "tavolo", "prevendita"):
            q = q.filter(Prenotazione.tipo == tipo)
        if stato in STATI:
            q = q.filter(Prenotazione.stato == stato)

        # Conta totale
        total = q.count()
        
        # Applica paginazione
        rows = q.order_by(Evento.data_evento.desc(), Prenotazione.id_prenotazione.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

        # Calcola pagine
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))

        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        return render_template("admin/prenotazioni_list.html", 
                             rows=rows, 
                             eventi=eventi,
                             filtro={"evento_id": evento_id, "tipo": tipo, "stato": stato},
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages,
                             pages_list=pages_list)
    finally:
        db.close()


@prenotazioni_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        clienti = db.query(Cliente).order_by(Cliente.cognome.asc(), Cliente.nome.asc()).all()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id", type=int)
            evento_id = request.form.get("evento_id", type=int)
            tipo = request.form.get("tipo")
            num_persone = request.form.get("num_persone", type=int)
            note = (request.form.get("note") or "").strip()
            orario_previsto = request.form.get("orario_previsto") or None
            stato = request.form.get("stato") or "attiva"

            if tipo not in ("lista", "tavolo", "prevendita"):
                flash("Tipo non valido.", "danger")
                return redirect(url_for("prenotazioni.admin_new"))

            # Regola anti-duplicato per attive
            if stato == "attiva" and _has_active_for_event(db, cliente_id, evento_id):
                flash("Esiste già una prenotazione attiva per questo cliente su questo evento.", "warning")
                return redirect(url_for("prenotazioni.admin_new"))

            if tipo == "tavolo":
                if not num_persone or num_persone < 1:
                    flash("Per tavolo, numero persone è obbligatorio.", "danger")
                    return redirect(url_for("prenotazioni.admin_new"))
                if not note:
                    flash("Per tavolo, note con nome tavolo obbligatorie.", "danger")
                    return redirect(url_for("prenotazioni.admin_new"))

            pren = Prenotazione(
                cliente_id=cliente_id,
                evento_id=evento_id,
                tipo=tipo,
                num_persone=num_persone if tipo == "tavolo" else None,
                orario_previsto=orario_previsto,
                note=note or None,
                stato=stato
            )
            db.add(pren)
            db.commit()
            if stato == "no-show":
                award_on_no_show(db, cliente_id=pren.cliente_id, evento_id=pren.evento_id)
            flash("Prenotazione creata.", "success")
            return redirect(url_for("prenotazioni.admin_prenotazione_detail", pren_id=pren.id_prenotazione))

        return render_template("admin/prenotazioni_form.html", e=None, eventi=eventi, clienti=clienti)
    finally:
        db.close()


@prenotazioni_bp.route("/admin/<int:pren_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(pren_id):
    db = SessionLocal()
    try:
        pren = db.query(Prenotazione).get(pren_id)
        if not pren:
            flash("Prenotazione non trovata.", "danger")
            return redirect(url_for("prenotazioni.admin_list"))

        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        clienti = db.query(Cliente).order_by(Cliente.cognome.asc(), Cliente.nome.asc()).all()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id", type=int)
            evento_id = request.form.get("evento_id", type=int)
            tipo = request.form.get("tipo")
            num_persone = request.form.get("num_persone", type=int)
            note = (request.form.get("note") or "").strip()
            orario_previsto = request.form.get("orario_previsto") or None
            stato = request.form.get("stato") or pren.stato

            if tipo not in ("lista", "tavolo", "prevendita"):
                flash("Tipo non valido.", "danger")
                return redirect(url_for("prenotazioni.admin_edit", pren_id=pren_id))

            # Anti-duplicato se diventa attiva e cambia coppia cliente/evento
            if stato == "attiva" and (cliente_id != pren.cliente_id or evento_id != pren.evento_id):
                if _has_active_for_event(db, cliente_id, evento_id):
                    flash("Esiste già una prenotazione attiva per questo cliente su questo evento.", "warning")
                    return redirect(url_for("prenotazioni.admin_edit", pren_id=pren_id))

            if tipo == "tavolo":
                if not num_persone or num_persone < 1:
                    flash("Per tavolo, numero persone è obbligatorio.", "danger")
                    return redirect(url_for("prenotazioni.admin_edit", pren_id=pren_id))
                if not note:
                    flash("Per tavolo, note con nome tavolo obbligatorie.", "danger")
                    return redirect(url_for("prenotazioni.admin_edit", pren_id=pren_id))

            pren.cliente_id = cliente_id
            pren.evento_id = evento_id
            pren.tipo = tipo
            pren.num_persone = num_persone if tipo == "tavolo" else None
            pren.note = note or None
            pren.orario_previsto = orario_previsto
            pren.stato = stato

            db.commit()
            if stato == "no-show":
                award_on_no_show(db, cliente_id=pren.cliente_id, evento_id=pren.evento_id)
            flash("Prenotazione aggiornata.", "success")
            return redirect(url_for("prenotazioni.admin_prenotazione_detail", pren_id=pren_id))

        return render_template("admin/prenotazioni_form.html", e=pren, eventi=eventi, clienti=clienti)
    finally:
        db.close()


@prenotazioni_bp.route("/admin/<int:pren_id>", methods=["GET"])
@require_admin
def admin_prenotazione_detail(pren_id):
    db = SessionLocal()
    try:
        from app.models.ingressi import Ingresso
        
        pren = db.query(Prenotazione).get(pren_id)
        if not pren:
            flash("Prenotazione non trovata.", "danger")
            return redirect(url_for("prenotazioni.admin_list"))
        
        # Carica relazioni
        cliente = db.query(Cliente).get(pren.cliente_id)
        evento = db.query(Evento).get(pren.evento_id)
        
        # Verifica se c'è un ingresso collegato
        ingresso = None
        if pren.id_prenotazione:
            ingresso = db.query(Ingresso).filter(Ingresso.prenotazione_id == pren.id_prenotazione).first()
        
        return render_template("admin/prenotazione_detail.html",
                             prenotazione=pren,
                             cliente=cliente,
                             evento=evento,
                             ingresso=ingresso)
    finally:
        db.close()


@prenotazioni_bp.route("/admin/<int:pren_id>/delete", methods=["POST"])
@require_admin
def admin_delete(pren_id):
    db = SessionLocal()
    try:
        pren = db.query(Prenotazione).get(pren_id)
        if pren:
            db.delete(pren)
            db.commit()
            flash("Prenotazione eliminata.", "warning")
        return redirect(url_for("prenotazioni.admin_list"))
    finally:
        db.close()


@prenotazioni_bp.route("/admin/<int:evento_id>/analytics", methods=["GET"])
@require_admin
def admin_analytics(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("prenotazioni.admin_list"))

        # Totali per tipo
        per_tipo = dict(db.query(Prenotazione.tipo, func.count(Prenotazione.id_prenotazione))
                          .filter(Prenotazione.evento_id == evento_id)
                          .group_by(Prenotazione.tipo).all())

        # Somma persone tavoli
        tavolo_persone = db.query(func.coalesce(func.sum(Prenotazione.num_persone), 0)) \
                           .filter(Prenotazione.evento_id == evento_id,
                                   Prenotazione.tipo == "tavolo") \
                           .scalar() or 0

        # Cancellazioni e no-show
        cancellazioni = db.query(func.count(Prenotazione.id_prenotazione)) \
                          .filter(Prenotazione.evento_id == evento_id,
                                  Prenotazione.stato == "cancellata").scalar() or 0

        no_show = db.query(func.count(Prenotazione.id_prenotazione)) \
                    .filter(Prenotazione.evento_id == evento_id,
                            Prenotazione.stato == "no-show").scalar() or 0

        return render_template("admin/prenotazioni_analytics.html",
                               e=e, per_tipo=per_tipo,
                               tavolo_persone=tavolo_persone,
                               cancellazioni=cancellazioni,
                               no_show=no_show)
    finally:
        db.close()