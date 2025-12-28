# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.clienti import Cliente
from app.models.staff import Staff
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.qr import generate_short_code
from app.utils.auth import hash_password
from app.utils.limiter import limiter
import os

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# -----------------------
# Helpers
# -----------------------
def _generate_unique_qr(db) -> str:
    while True:
        code = generate_short_code(10)
        if not db.query(Cliente).filter_by(qr_code=code).first():
            return code

def _clear_identities():
    # Sgombera eventuali sessioni pregresse
    session.pop("cliente_id", None)
    session.pop("staff_id", None)
    session.pop("staff_role", None)
    session.pop("admin_user", None)


def _looks_like_hash(value: str) -> bool:
    if not value:
        return False
    prefixes = (
        "pbkdf2:",
        "scrypt:",
        "bcrypt:",
        "$2b$",
        "$2a$",
        "$argon2",
    )
    return value.startswith(prefixes)


def _verify_and_upgrade_password(db, instance, field_name: str, password: str) -> bool:
    stored = getattr(instance, field_name, "") or ""
    if not stored:
        return False
    try:
        if _looks_like_hash(stored):
            return check_password_hash(stored, password)
    except ValueError:
        # continua con fallback legacy
        pass

    if stored == password:
        setattr(instance, field_name, hash_password(password))
        db.commit()
        return True

    return False

# -----------------------
# CLIENT — Register
# -----------------------
@auth_bp.route("/register", methods=["GET"])
def auth_register_form():
    return render_template("clienti/register.html")

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def auth_register_submit():
    nome = request.form.get("nome", "").strip()
    cognome = request.form.get("cognome", "").strip()
    telefono = request.form.get("telefono", "").strip()
    data_nascita = request.form.get("data_nascita") or None
    citta = request.form.get("citta", "").strip() or None
    password = request.form.get("password", "").strip()
    termini_accettati = request.form.get("accetto_termini") == "on"
    privacy_accettata = request.form.get("accetto_privacy") == "on"

    if not termini_accettati or not privacy_accettata:
        if not termini_accettati and not privacy_accettata:
            flash("Per proseguire devi accettare i Termini e Condizioni e la Privacy Policy.", "warning")
        elif not termini_accettati:
            flash("Per proseguire devi accettare i Termini e Condizioni.", "warning")
        else:
            flash("Per proseguire devi accettare la Privacy Policy.", "warning")
        return redirect(url_for("auth.auth_register_form"))

    if not all([nome, cognome, telefono, password]):
        flash("Per favore, compila tutti i campi obbligatori per completare la registrazione.", "warning")
        return redirect(url_for("auth.auth_register_form"))

    db = SessionLocal()
    try:
        qr = _generate_unique_qr(db)
        nuovo = Cliente(
            nome=nome,
            cognome=cognome,
            telefono=telefono,
            data_nascita=data_nascita,
            citta=citta,
            password_hash=generate_password_hash(password),
            qr_code=qr,
            livello="base",
            punti_fedelta=0,
            stato_account="attivo"
        )
        db.add(nuovo)
        db.commit()
        _clear_identities()
        session["cliente_id"] = nuovo.id_cliente
        flash("🎉 Benvenuto! Il tuo account è stato creato con successo.", "success")
        return redirect(url_for("clienti.area_personale"))
    except IntegrityError:
        db.rollback()
        flash("Sembra che questo numero sia già registrato. Hai già un account? Prova ad accedere.", "info")
        return redirect(url_for("auth.auth_login_cliente_form"))
    finally:
        db.close()

# -----------------------
# CLIENTE — Login Separato
# -----------------------
@auth_bp.route("/login-cliente", methods=["GET"])
def auth_login_cliente_form():
    """Login dedicato per i clienti"""
    return render_template("clienti/login.html")

@auth_bp.route("/login-cliente", methods=["POST"])
@limiter.limit("5 per minute")
def auth_login_cliente_submit():
    """Processa login cliente con rate limiting"""
    telefono = request.form.get("telefono", "").strip()
    password = request.form.get("password", "").strip()

    if not telefono or not password:
        flash("Per favore, inserisci il tuo numero di telefono e la password.", "warning")
        return redirect(url_for("auth.auth_login_cliente_form"))

    db = SessionLocal()
    try:
        cli = db.query(Cliente).filter(Cliente.telefono == telefono).first()
        if cli and _verify_and_upgrade_password(db, cli, "password_hash", password):
            if cli.stato_account == "disattivato":
                flash("Il tuo account risulta temporaneamente disattivato. Per assistenza, contattaci.", "danger")
                return redirect(url_for("auth.auth_login_cliente_form"))

            _clear_identities()
            session["cliente_id"] = cli.id_cliente
            flash(f"Bentornato, {cli.nome}! 👋", "success")
            return redirect(url_for("clienti.area_personale"))

        # Credenziali errate
        flash("Numero di telefono o password non corretti. Riprova.", "danger")
        return redirect(url_for("auth.auth_login_cliente_form"))
    finally:
        db.close()

# -----------------------
# STAFF — Login Separato
# -----------------------
@auth_bp.route("/login-staff", methods=["GET"])
def auth_login_staff_form():
    """Login dedicato per lo staff (baristi, ingressisti, admin)"""
    return render_template("staff/login.html")

@auth_bp.route("/login-staff", methods=["POST"])
@limiter.limit("5 per minute")
def auth_login_staff_submit():
    """Processa login staff con rate limiting"""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Per favore, inserisci username e password.", "warning")
        return redirect(url_for("auth.auth_login_staff_form"))

    db = SessionLocal()
    try:
        # Prova come STAFF (cerca per username)
        staff = db.query(Staff).filter(Staff.username == username).first()
        if staff:
            if not staff.attivo:
                flash("Il tuo account staff risulta disattivato. Contatta l'amministratore per assistenza.", "danger")
                return redirect(url_for("auth.auth_login_staff_form"))

            if _verify_and_upgrade_password(db, staff, "password_hash", password):
                _clear_identities()
                session["staff_id"] = staff.id_staff
                session["staff_role"] = staff.ruolo

                flash(f"Benvenuto, {staff.nome}! 🎯", "success")
                if staff.ruolo == "admin":
                    return redirect(url_for("dashboard.admin_dashboard"))
                return redirect(url_for("staff.home"))

        # Se non è staff, prova come ADMIN .env
        env_user = os.getenv("ADMIN_USER")
        env_pw_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
        env_pw_plain = os.getenv("ADMIN_PASSWORD", "").strip()

        if env_user and username == env_user:
            ok_pass = False
            
            if env_pw_hash:
                if env_pw_hash.startswith(("scrypt:", "pbkdf2:", "bcrypt:", "$2b$", "$2a$")):
                    ok_pass = check_password_hash(env_pw_hash, password)
                else:
                    ok_pass = (password == env_pw_hash)
            
            if not ok_pass and env_pw_plain:
                ok_pass = (password == env_pw_plain)

            if ok_pass:
                _clear_identities()
                session["staff_role"] = "admin"
                session["admin_user"] = env_user
                flash("Benvenuto, Amministratore! 🔐", "success")
                return redirect(url_for("dashboard.admin_dashboard"))

        # Credenziali errate
        flash("Username o password non corretti. Riprova.", "danger")
        return redirect(url_for("auth.auth_login_staff_form"))
    finally:
        db.close()

# -----------------------
# LOGIN UNIFICATO (Legacy - Deprecato)
# -----------------------
@auth_bp.route("/login", methods=["GET"])
def auth_login_form():
    """Login unificato legacy - reindirizza al login cliente"""
    flash("Questa pagina è deprecata. Usa il login dedicato.", "info")
    return redirect(url_for("auth.auth_login_cliente_form"))

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def auth_login_submit():
    """Login unificato legacy - reindirizza al login cliente"""
    flash("Questa pagina è deprecata. Usa il login dedicato.", "info")
    return redirect(url_for("auth.auth_login_cliente_form"))

@auth_bp.route("/logout")
def logout():
    """Logout universale - pulisce tutte le sessioni"""
    _clear_identities()
    flash("Disconnessione avvenuta con successo. A presto! 👋", "success")
    # Reindirizza in base al tipo di utente che era loggato
    if session.get("cliente_id"):
        return redirect(url_for("auth.auth_login_cliente_form"))
    else:
        return redirect(url_for("auth.auth_login_staff_form"))

# Route login-admin mantenuta per retrocompatibilità
@auth_bp.route("/login-admin", methods=["GET", "POST"])
def auth_admin_login_form():
    """Route legacy - reindirizza al login staff"""
    return redirect(url_for("auth.auth_login_staff_form"))