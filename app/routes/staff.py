from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from app.database import SessionLocal
from app.utils.decorators import require_staff, require_admin
from app.models.eventi import Evento
from app.models.staff import Staff
from werkzeug.security import generate_password_hash

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")
staff_admin_bp = Blueprint("staff_admin", __name__, url_prefix="/admin/staff")

# ---------- STAFF ----------
@staff_bp.route("/")
@require_staff
def dashboard():
    db = SessionLocal()
    try:
        evento_attivo = db.query(Evento).filter_by(stato="attivo").order_by(Evento.data_evento.desc()).first()
        return render_template("staff/dashboard.html", evento_attivo=evento_attivo)
    finally:
        db.close()

@staff_bp.route("/evento-attivo")
@require_staff
def evento_attivo_view():
    db = SessionLocal()
    try:
        evento_attivo = db.query(Evento).filter_by(stato="attivo").order_by(Evento.data_evento.desc()).first()
        return render_template("staff/evento_attivo.html", evento_attivo=evento_attivo)
    finally:
        db.close()

# ---------- ADMIN: imposta/chiudi evento attivo globale ----------
@staff_admin_bp.route("/evento-attivo", methods=["GET"])
@require_admin
def set_active_form():
    db = SessionLocal()
    try:
        eventi = db.query(Evento).filter(Evento.data_evento >= date.today()).order_by(Evento.data_evento.asc()).all()
        evento_attivo = db.query(Evento).filter_by(stato="attivo").first()
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

        # Chiudi tutti gli eventi
        for ev in db.query(Evento).all():
            ev.stato = "chiuso"

        # Attiva quello scelto
        ev = db.query(Evento).get(int(evento_id))
        if not ev:
            flash("Evento non trovato.", "error")
            return redirect(url_for("staff_admin.set_active_form"))
        ev.stato = "attivo"

        db.commit()
        current_app.config["EVENTO_ATTIVO_ID"] = ev.id_evento
        flash(f"Evento attivo impostato: {ev.nome_evento} - {ev.data_evento}", "success")
        return redirect(url_for("staff_admin.set_active_form"))
    finally:
        db.close()

@staff_admin_bp.route("/chiudi-evento", methods=["POST"])
@require_admin
def close_active():
    db = SessionLocal()
    try:
        ev = db.query(Evento).filter_by(stato="attivo").first()
        if not ev:
            flash("Nessun evento attivo da chiudere.", "warning")
            return redirect(url_for("staff_admin.set_active_form"))
        ev.stato = "chiuso"
        db.commit()
        current_app.config["EVENTO_ATTIVO_ID"] = None
        flash("Evento chiuso. La discoteca è ora chiusa.", "success")
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
        if ruolo in ("admin", "staff", "barista", "cassa"):
            q = q.filter(Staff.ruolo == ruolo)
        if attivo == "true":
            q = q.filter(Staff.attivo == True)
        elif attivo == "false":
            q = q.filter(Staff.attivo == False)
        
        staff_list = q.order_by(Staff.nome.asc()).all()
        return render_template("admin/staff_list.html", staff_list=staff_list,
                               filtro={"ruolo": ruolo, "attivo": attivo})
    finally:
        db.close()

@staff_admin_bp.route("/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            ruolo = request.form.get("ruolo")
            attivo = request.form.get("attivo") == "on"
            
            if not all([nome, username, password]):
                flash("Compila tutti i campi obbligatori.", "danger")
                return redirect(url_for("staff_admin.admin_new"))
            
            if ruolo not in ("admin", "staff", "barista", "cassa"):
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
        
        return render_template("admin/staff_form.html", s=None)
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
        
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            ruolo = request.form.get("ruolo")
            attivo = request.form.get("attivo") == "on"
            
            if not all([nome, username]):
                flash("Nome e username obbligatori.", "danger")
                return redirect(url_for("staff_admin.admin_edit", staff_id=staff_id))
            
            if ruolo not in ("admin", "staff", "barista", "cassa"):
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
        
        return render_template("admin/staff_form.html", s=s)
    finally:
        db.close()

@staff_admin_bp.route("/<int:staff_id>/delete", methods=["POST"])
@require_admin
def admin_delete(staff_id):
    db = SessionLocal()
    try:
        s = db.query(Staff).get(staff_id)
        if s:
            # Soft delete: disattiva invece di eliminare
            s.attivo = False
            db.commit()
            flash("Staff disattivato.", "warning")
        return redirect(url_for("staff_admin.admin_list"))
    finally:
        db.close()

@staff_admin_bp.route("/<int:staff_id>/activate", methods=["POST"])
@require_admin
def admin_activate(staff_id):
    db = SessionLocal()
    try:
        s = db.query(Staff).get(staff_id)
        if s:
            s.attivo = True
            db.commit()
            flash("Staff riattivato.", "success")
        return redirect(url_for("staff_admin.admin_list"))
    finally:
        db.close()