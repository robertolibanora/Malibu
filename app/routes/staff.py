from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from app.database import SessionLocal
from app.utils.decorators import require_staff, require_admin
from app.models.eventi import Evento
from app.models.staff import Staff
from werkzeug.security import generate_password_hash
from app.utils.events import get_evento_operativo, set_evento_operativo_id
from app.routes.log_attivita import log_action

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
    db = SessionLocal()
    try:
        evento_attivo = get_evento_operativo(db)
        return render_template("staff/home.html", evento_attivo=evento_attivo)
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

@staff_admin_bp.route("/<int:staff_id>/delete", methods=["POST"])
@require_admin
def admin_delete(staff_id):
    db = SessionLocal()
    try:
        s = db.query(Staff).get(staff_id)
        if s:
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