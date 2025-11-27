from flask import Flask, redirect, url_for, render_template
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from app.database import engine, Base
from dotenv import load_dotenv
import os
from pathlib import Path
from app.routes import all_blueprints  # ✅ import centralizzato
from app.routes.staff import staff_bp, staff_admin_bp
from app.utils.limiter import init_limiter

def create_app():
    load_dotenv()
    # Percorso assoluto alla directory templates e static (relativo alla root del progetto)
    base_dir = Path(__file__).parent.parent
    template_dir = base_dir / 'templates'
    static_dir = base_dir / 'static'
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.secret_key = os.getenv("SECRET_KEY")
    
    # ⚡ Configurazione Rate Limiting
    limiter = init_limiter(app)
    app.limiter = limiter

    # Configurazione database
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+mysqlconnector://{db_user}:{db_password or ''}@{db_host}:{db_port or '3306'}/{db_name}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config.setdefault("EVENTO_ATTIVO_ID", None)
    
    # Configurazione upload file
    app.config['UPLOAD_FOLDER'] = str(static_dir / 'uploads' / 'eventi')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
    
    # Crea la cartella uploads se non esiste
    upload_dir = Path(app.config['UPLOAD_FOLDER'])
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Inizializza database
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    try:
        feedback_columns = {col["name"] for col in inspector.get_columns("feedback")}
        if "voto_servizio" not in feedback_columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE feedback "
                    "ADD COLUMN voto_servizio SMALLINT NOT NULL DEFAULT 5"
                ))
                conn.execute(text(
                    "ALTER TABLE feedback "
                    "ADD CONSTRAINT chk_voto_servizio "
                    "CHECK (voto_servizio BETWEEN 1 AND 10)"
                ))
        staff_columns = inspector.get_columns("staff")
        ruolo_column = next((col for col in staff_columns if col["name"] == "ruolo"), None)
        desired_roles = ("admin", "barista", "ingressista")
        legacy_roles = ("staff", "cassa")
        if ruolo_column:
            current_roles = tuple(getattr(ruolo_column["type"], "enums", ()))
            has_all_desired = all(role in current_roles for role in desired_roles)
            legacy_present = any(role in current_roles for role in legacy_roles)
            needs_cleanup = (set(current_roles) ^ set(desired_roles)) or legacy_present or not has_all_desired

            if needs_cleanup:
                # Step 1: assicurati che i valori legacy + nuovi siano ammessi prima dell'update
                extended_roles = tuple(dict.fromkeys(current_roles + desired_roles + legacy_roles))
                if set(extended_roles) != set(current_roles):
                    default_role = "staff" if "staff" in extended_roles else desired_roles[-1]
                    enum_literal = ",".join(f"'{r}'" for r in extended_roles)
                    with engine.begin() as conn:
                        conn.execute(text(
                            f"ALTER TABLE staff "
                            f"MODIFY ruolo ENUM({enum_literal}) "
                            f"NOT NULL DEFAULT '{default_role}'"
                        ))

                # Step 2: normalizza i dati esistenti
                with engine.begin() as conn:
                    conn.execute(text(
                        "UPDATE staff SET ruolo = 'ingressista' "
                        "WHERE ruolo = 'staff'"
                    ))
                    conn.execute(text(
                        "UPDATE staff SET ruolo = 'barista' "
                        "WHERE ruolo = 'cassa'"
                    ))

                # Step 3: imposta definitivamente l'enum ai soli valori ammessi
                enum_literal = ",".join(f"'{r}'" for r in desired_roles)
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE staff "
                        f"MODIFY ruolo ENUM({enum_literal}) "
                        f"NOT NULL DEFAULT 'ingressista'"
                    ))
    except Exception as exc:
        # Evita di bloccare l'avvio dell'app: logga l'errore e prosegui.
        if app.logger:
            app.logger.error("Impossibile sincronizzare le migrazioni automatiche: %s", exc)

    # Route root: reindirizza al login cliente (pubblico)
    @app.route("/")
    def root():
        return redirect(url_for("auth.auth_login_cliente_form"))

    # Error handlers
    @app.errorhandler(401)
    def unauthorized(e):
        return render_template("shared/401.html"), 401

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("shared/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("shared/404.html"), 404
    
    # Rate limiting error handler
    from flask_limiter.errors import RateLimitExceeded
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        from flask import flash, redirect, url_for, session
        flash("Troppe richieste. Attendi qualche istante prima di riprovare.", "warning")
        # Reindirizza in base al tipo di utente
        if session.get("cliente_id"):
            return redirect(url_for("clienti.area_personale"))
        elif session.get("staff_id"):
            return redirect(url_for("staff.home"))
        else:
            return redirect(url_for("auth.auth_login_cliente_form")), 429

    # Registra automaticamente tutti i blueprint
    for bp in all_blueprints:
        app.register_blueprint(bp)

    # Registra blueprint staff
    app.register_blueprint(staff_bp)
    app.register_blueprint(staff_admin_bp)

    return app