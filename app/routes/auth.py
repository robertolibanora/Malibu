# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.clienti import Cliente
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.qr import generate_short_code
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
    session.pop("staff_role", None)
    session.pop("admin_user", None)

# -----------------------
# CLIENT — Register
# -----------------------
@auth_bp.route("/register", methods=["GET"])
def auth_register_form():
    return render_template("shared/register.html")

@auth_bp.route("/register", methods=["POST"])
def auth_register_submit():
    nome = request.form.get("nome", "").strip()
    cognome = request.form.get("cognome", "").strip()
    telefono = request.form.get("telefono", "").strip()
    data_nascita = request.form.get("data_nascita") or None
    citta = request.form.get("citta", "").strip() or None
    password = request.form.get("password", "").strip()

    if not all([nome, cognome, telefono, password]):
        flash("Compila tutti i campi obbligatori.", "danger")
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
        flash("Registrazione completata!", "success")
        return redirect(url_for("clienti.area_personale"))
    except IntegrityError:
        db.rollback()
        flash("Telefono o email già registrati. Se è tuo, fai il login.", "warning")
        return redirect(url_for("auth.auth_register_form"))
    finally:
        db.close()

# -----------------------
# UNIFIED LOGIN — Cliente o Admin
# -----------------------
@auth_bp.route("/login", methods=["GET"])
def auth_login_form():
    return render_template("shared/login.html")

@auth_bp.route("/login", methods=["POST"])
def auth_login_submit():
    identifier = request.form.get("identifier", "").strip()
    password = request.form.get("password", "").strip()

    if not identifier or not password:
        flash("Compila tutti i campi.", "danger")
        return redirect(url_for("auth.auth_login_form"))

    db = SessionLocal()
    try:
        # Prova prima come CLIENTE (cerca per telefono)
        cli = db.query(Cliente).filter(Cliente.telefono == identifier).first()
        if cli and cli.password_hash and check_password_hash(cli.password_hash, password):
            if cli.stato_account == "disattivato":
                flash("Account disattivato. Contatta l'assistenza.", "danger")
                return redirect(url_for("auth.auth_login_form"))

            _clear_identities()
            session["cliente_id"] = cli.id_cliente
            flash("Login eseguito.", "success")
            return redirect(url_for("clienti.area_personale"))

        # Se non è un cliente, prova come ADMIN (cerca per username)
        env_user = os.getenv("ADMIN_USER")
        env_pw_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
        env_pw_plain = os.getenv("ADMIN_PASSWORD", "").strip()

        if env_user and identifier == env_user:
            ok_pass = False
            
            # Se esiste ADMIN_PASSWORD_HASH, verifica se è un hash valido o una password in chiaro
            if env_pw_hash:
                # Controlla se è un hash valido (inizia con algoritmo: scrypt:, pbkdf2:, ecc.)
                if env_pw_hash.startswith(("scrypt:", "pbkdf2:", "bcrypt:", "$2b$", "$2a$")):
                    # È un hash valido, verifica con check_password_hash
                    ok_pass = check_password_hash(env_pw_hash, password)
                else:
                    # Non è un hash, tratta come password in chiaro
                    ok_pass = (password == env_pw_hash)
            
            # Se non c'è hash o non ha funzionato, prova con ADMIN_PASSWORD
            if not ok_pass and env_pw_plain:
                ok_pass = (password == env_pw_plain)

            if ok_pass:
                _clear_identities()
                session["staff_role"] = "admin"
                session["admin_user"] = env_user
                flash("Benvenuto, admin.", "success")
                return redirect(url_for("clienti.admin_dashboard"))

        # Nessuna corrispondenza trovata
        flash("Credenziali non valide.", "danger")
        return redirect(url_for("auth.auth_login_form"))
    finally:
        db.close()

@auth_bp.route("/logout")
def logout():
    _clear_identities()
    flash("Logout eseguito.", "success")
    return redirect(url_for("auth.auth_login_form"))

# Route login-admin mantenuta per retrocompatibilità, ma reindirizza al login unificato
@auth_bp.route("/login-admin", methods=["GET", "POST"])
def auth_admin_login_form():
    # Reindirizza al login unificato
    return redirect(url_for("auth.auth_login_form"))