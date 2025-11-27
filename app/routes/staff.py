from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.database import SessionLocal
from app.utils.decorators import require_staff, require_admin
from app.models.eventi import Evento
from app.models.staff import Staff
from werkzeug.security import generate_password_hash
from app.utils.events import get_evento_operativo, set_evento_operativo_id
from app.routes.log_attivita import log_action
from app.utils.limiter import limiter

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")
staff_admin_bp = Blueprint("staff_admin", __name__, url_prefix="/admin/staff")

OPERATIVE_ROLES = ("ingressista", "barista")
ROLE_LABELS = {
    "admin": "Admin",
    "ingressista": "Ingressista",
    "barista": "Barista",
}
FILTERABLE_ROLES = ("admin",) + OPERATIVE_ROLES

# ---------- STAFF ----------
@staff_bp.route("/")
@require_staff
def home():
    """Home staff - reindirizza allo scanner unificato se c'è evento attivo"""
    db = SessionLocal()
    try:
        evento_attivo = get_evento_operativo(db)
        staff_role = session.get("staff_role", "")
        
        # Per operatori (ingressista/barista) reindirizza direttamente allo scanner
        if evento_attivo and staff_role in OPERATIVE_ROLES:
            return redirect(url_for("staff.scan_unificato"))
        
        return render_template("staff/home.html", evento_attivo=evento_attivo, staff_role=staff_role)
    finally:
        db.close()


@staff_bp.route("/scan")
@require_staff
def scan_unificato():
    """Scanner unificato - porta d'ingresso principale per tutti gli operatori"""
    from sqlalchemy import func
    from app.models.ingressi import Ingresso
    from app.models.prodotti import Prodotto
    from app.models.prenotazioni import Prenotazione
    
    db = SessionLocal()
    try:
        evento = get_evento_operativo(db)
        if not evento:
            flash("Nessun evento operativo attivo.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        
        staff_role = session.get("staff_role", "")
        
        # Statistiche evento
        ingressi_totali = db.query(func.count(Ingresso.id_ingresso)).filter(
            Ingresso.evento_id == evento.id_evento
        ).scalar() or 0
        
        capienza_residua = None
        if evento.capienza_max:
            capienza_residua = evento.capienza_max - ingressi_totali
        
        prenotati_attesa = db.query(func.count(Prenotazione.id_prenotazione)).filter(
            Prenotazione.evento_id == evento.id_evento,
            Prenotazione.stato == "attiva"
        ).scalar() or 0
        
        # Prodotti per il barista (raggruppati per categoria)
        prodotti_per_categoria = {}
        if staff_role in ("barista", "admin"):
            prodotti = db.query(Prodotto).filter(Prodotto.attivo == True).order_by(
                Prodotto.categoria.asc(), Prodotto.nome.asc()
            ).all()
            for p in prodotti:
                cat = p.categoria or "Altro"
                if cat not in prodotti_per_categoria:
                    prodotti_per_categoria[cat] = []
                prodotti_per_categoria[cat].append(p)
        
        return render_template("staff/scan_unificato.html",
                             evento=evento,
                             staff_role=staff_role,
                             ingressi_totali=ingressi_totali,
                             capienza_residua=capienza_residua,
                             prenotati_attesa=prenotati_attesa,
                             prodotti_per_categoria=prodotti_per_categoria)
    finally:
        db.close()


@staff_bp.route("/scan/cliente-info", methods=["POST"])
@require_staff
def scan_cliente_info():
    """API per ottenere info cliente dopo scansione QR (usato dallo scanner unificato)"""
    from flask import jsonify
    from app.models.clienti import Cliente
    from app.models.ingressi import Ingresso
    from app.models.prenotazioni import Prenotazione
    
    db = SessionLocal()
    try:
        data = request.get_json() or {}
        qr = (data.get("qr") or "").strip()
        
        if not qr:
            return jsonify({"ok": False, "reason": "missing_qr"})
        
        evento = get_evento_operativo(db)
        if not evento:
            return jsonify({"ok": False, "reason": "no_event"})
        
        cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
        if not cli:
            return jsonify({"ok": False, "reason": "not_found"})
        
        # Check ingresso
        ingresso = db.query(Ingresso).filter(
            Ingresso.cliente_id == cli.id_cliente,
            Ingresso.evento_id == evento.id_evento
        ).first()
        
        # Check prenotazione
        prenotazione = db.query(Prenotazione).filter(
            Prenotazione.cliente_id == cli.id_cliente,
            Prenotazione.evento_id == evento.id_evento,
            Prenotazione.stato == "attiva"
        ).first()
        
        return jsonify({
            "ok": True,
            "cliente": {
                "id": cli.id_cliente,
                "nome": cli.nome,
                "cognome": cli.cognome,
                "livello": cli.livello,
                "punti": cli.punti_fedelta or 0,
                "data_nascita": cli.data_nascita.strftime("%d/%m/%Y") if cli.data_nascita else None,
                "citta": cli.citta
            },
            "ha_ingresso": ingresso is not None,
            "ingresso_id": ingresso.id_ingresso if ingresso else None,
            "ha_prenotazione": prenotazione is not None,
            "prenotazione": {
                "id": prenotazione.id_prenotazione,
                "tipo": prenotazione.tipo,
                "num_persone": prenotazione.num_persone,
                "note": prenotazione.note
            } if prenotazione else None
        })
    finally:
        db.close()


@staff_bp.route("/scan/registra-ingresso", methods=["POST"])
@require_staff
@limiter.limit("30 per minute", key_func=lambda: session.get("staff_id") or request.remote_addr)
def scan_registra_ingresso():
    """API per registrare ingresso rapido (usato dallo scanner unificato)"""
    from flask import jsonify
    from app.models.clienti import Cliente
    from app.models.ingressi import Ingresso
    from app.models.prenotazioni import Prenotazione
    from app.routes.fedelta import award_on_ingresso
    
    db = SessionLocal()
    try:
        data = request.get_json() or {}
        qr = (data.get("qr") or "").strip()
        
        if not qr:
            return jsonify({"ok": False, "error": "QR mancante"})
        
        evento = get_evento_operativo(db)
        if not evento:
            return jsonify({"ok": False, "error": "Nessun evento attivo"})
        
        cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
        if not cli:
            return jsonify({"ok": False, "error": "Cliente non trovato"})
        
        # Check se già entrato
        existing = db.query(Ingresso).filter(
            Ingresso.cliente_id == cli.id_cliente,
            Ingresso.evento_id == evento.id_evento
        ).first()
        
        if existing:
            return jsonify({"ok": False, "error": "Cliente già entrato", "already": True})
        
        # Determina tipo ingresso dalla prenotazione
        prenotazione = db.query(Prenotazione).filter(
            Prenotazione.cliente_id == cli.id_cliente,
            Prenotazione.evento_id == evento.id_evento,
            Prenotazione.stato == "attiva"
        ).first()
        
        tipo_ingresso = "lista"
        if prenotazione:
            tipo_ingresso = prenotazione.tipo
            prenotazione.stato = "usata"
            # Log prenotazione usata
            log_action(
                db,
                tabella="prenotazioni",
                record_id=prenotazione.id_prenotazione,
                staff_id=session.get("staff_id"),
                azione="prenotazione_usata",
                note=f"evento_id={evento.id_evento}"
            )
        
        # Crea ingresso
        ingresso = Ingresso(
            cliente_id=cli.id_cliente,
            evento_id=evento.id_evento,
            prenotazione_id=prenotazione.id_prenotazione if prenotazione else None,
            tipo_ingresso=tipo_ingresso,
            staff_id=session.get("staff_id")
        )
        db.add(ingresso)
        db.flush()
        
        # Award punti fedeltà (passa has_prenotazione)
        award_on_ingresso(db, cli.id_cliente, evento.id_evento, has_prenotazione=(prenotazione is not None))
        
        # Log ingresso
        log_action(
            db,
            tabella="ingressi",
            record_id=ingresso.id_ingresso,
            staff_id=session.get("staff_id"),
            azione="ingresso_registrato",
            note=f"evento_id={evento.id_evento}, tipo={tipo_ingresso}"
        )
        
        db.commit()
        
        return jsonify({
            "ok": True,
            "ingresso_id": ingresso.id_ingresso,
            "cliente_nome": f"{cli.nome} {cli.cognome}",
            "tipo": tipo_ingresso
        })
    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})
    finally:
        db.close()


@staff_bp.route("/evento-attivo")
@require_staff
def evento_attivo_view():
    db = SessionLocal()
    try:
        evento_attivo = get_evento_operativo(db)
        return render_template("staff/evento_attivo.html", evento_attivo=evento_attivo)
    finally:
        db.close()

# ---------- ADMIN: imposta/chiudi evento attivo globale ----------
@staff_admin_bp.route("/evento-attivo", methods=["GET"])
@require_admin
def set_active_form():
    db = SessionLocal()
    try:
        window_start = date.today() - date.resolution  # ieri incluso
        eventi = db.query(Evento).filter(Evento.data_evento >= window_start).order_by(Evento.data_evento.asc()).all()
        evento_attivo = get_evento_operativo(db)
        return render_template("admin/evento_attivo.html", eventi=eventi, evento_attivo=evento_attivo)
    finally:
        db.close()

@staff_admin_bp.route("/evento-attivo", methods=["POST"])
@require_admin
def set_active_post():
    db = SessionLocal()
    try:
        evento_id = request.form.get("evento_id")
        if not evento_id:
            flash("Seleziona un evento.", "error")
            return redirect(url_for("staff_admin.set_active_form"))

        # Disattiva tutti e abilita quello scelto
        for ev in db.query(Evento).filter(Evento.is_staff_operativo == True).all():
            ev.is_staff_operativo = False
        ev = db.query(Evento).get(int(evento_id))
        if not ev:
            flash("Evento non trovato.", "error")
            return redirect(url_for("staff_admin.set_active_form"))
        ev.is_staff_operativo = True

        db.commit()
        set_evento_operativo_id(db, ev.id_evento)
        log_action(db, tabella="eventi", record_id=ev.id_evento, staff_id=session.get("staff_id"), azione="set_operativo")
        flash(f"Evento operativo impostato: {ev.nome_evento} - {ev.data_evento}", "success")
        return redirect(url_for("staff_admin.set_active_form"))
    finally:
        db.close()

@staff_admin_bp.route("/chiudi-evento", methods=["POST"])
@require_admin
def close_active():
    db = SessionLocal()
    try:
        ev = get_evento_operativo(db)
        if not ev:
            flash("Nessun evento attivo da chiudere.", "warning")
            return redirect(url_for("staff_admin.set_active_form"))
        ev.is_staff_operativo = False
        db.commit()
        set_evento_operativo_id(db, None)
        log_action(db, tabella="eventi", record_id=(ev.id_evento if ev else 0), staff_id=session.get("staff_id"), azione="unset_operativo")
        flash("Evento operativo disattivato. La discoteca è ora chiusa.", "success")
        return redirect(url_for("staff_admin.set_active_form"))
    finally:
        db.close()

# ============================================
# 👑 ADMIN — Hub Impostazioni (pagina centrale)
# ============================================
@staff_admin_bp.route("/hub", methods=["GET"])
@require_admin
def admin_hub():
    """Hub centrale per tutte le impostazioni del sistema"""
    from app.models.prodotti import Prodotto
    from app.models.template_eventi import TemplateEvento
    from app.models.soglie_fedelta import SogliaFedelta
    
    db = SessionLocal()
    try:
        # Statistiche rapide per ogni sezione
        tot_staff = db.query(Staff).count()
        staff_attivi = db.query(Staff).filter(Staff.attivo == True).count()
        
        tot_prodotti = db.query(Prodotto).count()
        prodotti_attivi = db.query(Prodotto).filter(Prodotto.attivo == True).count()
        
        tot_format = db.query(TemplateEvento).count()
        
        # Soglie fedeltà
        soglie = db.query(SogliaFedelta).order_by(SogliaFedelta.punti_min.asc()).all()
        
        return render_template("admin/impostazioni_hub.html",
                             tot_staff=tot_staff,
                             staff_attivi=staff_attivi,
                             tot_prodotti=tot_prodotti,
                             prodotti_attivi=prodotti_attivi,
                             tot_format=tot_format,
                             soglie=soglie)
    finally:
        db.close()


# ============================================
# 👑 ADMIN — Gestione Staff (CRUD)
# ============================================
@staff_admin_bp.route("/", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        ruolo = request.args.get("ruolo")
        attivo = request.args.get("attivo")
        
        q = db.query(Staff)
        if ruolo not in FILTERABLE_ROLES:
            ruolo = None
        if ruolo:
            q = q.filter(Staff.ruolo == ruolo)
        if attivo == "true":
            q = q.filter(Staff.attivo == True)
        elif attivo == "false":
            q = q.filter(Staff.attivo == False)
        
        staff_list = q.order_by(Staff.nome.asc()).all()
        return render_template(
            "admin/staff_list.html",
            staff_list=staff_list,
            filtro={"ruolo": ruolo, "attivo": attivo},
            role_labels=ROLE_LABELS,
            filter_roles=FILTERABLE_ROLES
        )
    finally:
        db.close()

@staff_admin_bp.route("/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        role_choices = [(code, ROLE_LABELS[code]) for code in OPERATIVE_ROLES]

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            ruolo = request.form.get("ruolo")
            attivo = request.form.get("attivo") == "on"
            
            if not all([nome, username, password]):
                flash("Compila tutti i campi obbligatori.", "danger")
                return redirect(url_for("staff_admin.admin_new"))
            
            if ruolo not in dict(role_choices):
                flash("Ruolo non valido.", "danger")
                return redirect(url_for("staff_admin.admin_new"))
            
            # Verifica username unico
            existing = db.query(Staff).filter(Staff.username == username).first()
            if existing:
                flash("Username già in uso.", "danger")
                return redirect(url_for("staff_admin.admin_new"))
            
            nuovo = Staff(
                nome=nome,
                username=username,
                password_hash=generate_password_hash(password),
                ruolo=ruolo,
                attivo=attivo
            )
            db.add(nuovo)
            db.commit()
            flash("Staff creato.", "success")
            return redirect(url_for("staff_admin.admin_list"))
        
        return render_template("admin/staff_form.html", s=None, role_choices=role_choices, role_locked=False)
    finally:
        db.close()

@staff_admin_bp.route("/<int:staff_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(staff_id):
    db = SessionLocal()
    try:
        s = db.query(Staff).get(staff_id)
        if not s:
            flash("Staff non trovato.", "danger")
            return redirect(url_for("staff_admin.admin_list"))
        
        if s.ruolo == "admin":
            role_choices = [("admin", ROLE_LABELS["admin"])]
            role_locked = True
        else:
            role_choices = [(code, ROLE_LABELS[code]) for code in OPERATIVE_ROLES]
            role_locked = False

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            ruolo = request.form.get("ruolo")
            attivo = request.form.get("attivo") == "on"
            
            if not all([nome, username]):
                flash("Nome e username obbligatori.", "danger")
                return redirect(url_for("staff_admin.admin_edit", staff_id=staff_id))
            
            if s.ruolo == "admin":
                ruolo = "admin"
            elif ruolo not in dict(role_choices):
                flash("Ruolo non valido.", "danger")
                return redirect(url_for("staff_admin.admin_edit", staff_id=staff_id))
            
            # Verifica username unico (escludendo se stesso)
            existing = db.query(Staff).filter(
                Staff.username == username,
                Staff.id_staff != staff_id
            ).first()
            if existing:
                flash("Username già in uso.", "danger")
                return redirect(url_for("staff_admin.admin_edit", staff_id=staff_id))
            
            s.nome = nome
            s.username = username
            s.ruolo = ruolo
            s.attivo = attivo
            
            # Aggiorna password solo se fornita
            if password:
                s.password_hash = generate_password_hash(password)
            
            db.commit()
            flash("Staff aggiornato.", "success")
            return redirect(url_for("staff_admin.admin_list"))
        
        return render_template("admin/staff_form.html", s=s, role_choices=role_choices, role_locked=role_locked)
    finally:
        db.close()

@staff_admin_bp.route("/<int:staff_id>/delete", methods=["GET", "POST"])
@require_admin
def admin_delete(staff_id):
    db = SessionLocal()
    try:
        s = db.query(Staff).get(staff_id)
        if not s:
            flash("Staff non trovato.", "danger")
            return redirect(url_for("staff_admin.admin_list"))
        
        # Se GET, reindirizza alla lista (operazione di eliminazione richiede POST)
        if request.method == "GET":
            flash("Per eliminare uno staff, usa il pulsante Elimina nella lista.", "info")
            return redirect(url_for("staff_admin.admin_list"))
        
        # POST: elimina lo staff
        db.delete(s)
        db.commit()
        flash("Staff eliminato.", "warning")
        return redirect(url_for("staff_admin.admin_list"))
    finally:
        db.close()

@staff_admin_bp.route("/<int:staff_id>/activate", methods=["POST"])
@require_admin
def admin_activate(staff_id):
    db = SessionLocal()
    try:
        # Non più supportato: la logica di riattivazione è stata sostituita dall'eliminazione definitiva
        flash("Operazione non disponibile. I profili staff si eliminano definitivamente.", "warning")
        return redirect(url_for("staff_admin.admin_list"))
    finally:
        db.close()