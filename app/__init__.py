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
    use_sqlite = os.getenv("USE_SQLITE", "false").lower() == "true"
    if use_sqlite:
        db_path = base_dir / "malibu.db"
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    else:
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
    # Verifica se stiamo usando SQLite (non supporta ALTER TABLE MODIFY)
    is_sqlite = engine.dialect.name == "sqlite"
    
    try:
        feedback_columns = {col["name"] for col in inspector.get_columns("feedback")}
        if "voto_servizio" not in feedback_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE feedback "
                        "ADD COLUMN voto_servizio SMALLINT DEFAULT 5"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE feedback "
                        "ADD COLUMN voto_servizio SMALLINT NOT NULL DEFAULT 5"
                    ))
                    conn.execute(text(
                        "ALTER TABLE feedback "
                        "ADD CONSTRAINT chk_voto_servizio "
                        "CHECK (voto_servizio BETWEEN 1 AND 10)"
                    ))

        # Migrazione: aggiungi colonne per apertura/chiusura automatica eventi
        eventi_columns = {col["name"] for col in inspector.get_columns("eventi")}
        if "data_ora_apertura_auto" not in eventi_columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE eventi "
                    "ADD COLUMN data_ora_apertura_auto DATETIME NULL"
                ))
        if "data_ora_chiusura_auto" not in eventi_columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE eventi "
                    "ADD COLUMN data_ora_chiusura_auto DATETIME NULL"
                ))
        
        prenotazioni_columns = {col["name"] for col in inspector.get_columns("prenotazioni")}
        if "ruolo_tavolo" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    # SQLite: usa VARCHAR invece di ENUM, senza AFTER
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN ruolo_tavolo VARCHAR(20) NOT NULL DEFAULT 'none'"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN ruolo_tavolo ENUM('referente', 'aderente', 'none') "
                        "NOT NULL DEFAULT 'none' "
                        "AFTER stato"
                    ))
        if "prenotazione_padre_id" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN prenotazione_padre_id INTEGER NULL"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN prenotazione_padre_id INT NULL "
                        "AFTER ruolo_tavolo"
                    ))
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD CONSTRAINT fk_prenotazioni_padre "
                        "FOREIGN KEY (prenotazione_padre_id) "
                        "REFERENCES prenotazioni(id_prenotazione) "
                        "ON DELETE CASCADE ON UPDATE CASCADE"
                    ))
        if "codice_invito" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    # SQLite non supporta UNIQUE in ALTER TABLE ADD COLUMN
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN codice_invito VARCHAR(10)"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN codice_invito VARCHAR(10) UNIQUE "
                        "AFTER prenotazione_padre_id"
                    ))
        if "numero_tavolo" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN numero_tavolo INTEGER NULL"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN numero_tavolo INT NULL "
                        "AFTER codice_invito"
                    ))
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD CONSTRAINT fk_prenotazioni_tavolo "
                        "FOREIGN KEY (numero_tavolo) "
                        "REFERENCES tavoli_evento(id_tavolo) "
                        "ON DELETE SET NULL ON UPDATE CASCADE"
                    ))
        if "nome_tavolo_gruppo" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN nome_tavolo_gruppo VARCHAR(100)"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN nome_tavolo_gruppo VARCHAR(100) "
                        "AFTER numero_tavolo"
                    ))
        if "stato_approvazione_tavolo" not in prenotazioni_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    # SQLite: usa VARCHAR invece di ENUM
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN stato_approvazione_tavolo VARCHAR(20) DEFAULT NULL"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE prenotazioni "
                        "ADD COLUMN stato_approvazione_tavolo "
                        "ENUM('in_attesa','approvata','rifiutata') "
                        "DEFAULT NULL "
                        "AFTER nome_tavolo_gruppo"
                    ))
        # Migrazione: aggiungi colonne per apertura/chiusura automatica eventi
        eventi_columns = {col["name"] for col in inspector.get_columns("eventi")}
        if "data_ora_apertura_auto" not in eventi_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE eventi "
                        "ADD COLUMN data_ora_apertura_auto DATETIME NULL"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE eventi "
                        "ADD COLUMN data_ora_apertura_auto DATETIME NULL"
                    ))
        if "data_ora_chiusura_auto" not in eventi_columns:
            with engine.begin() as conn:
                if is_sqlite:
                    conn.execute(text(
                        "ALTER TABLE eventi "
                        "ADD COLUMN data_ora_chiusura_auto DATETIME NULL"
                    ))
                else:
                    conn.execute(text(
                        "ALTER TABLE eventi "
                        "ADD COLUMN data_ora_chiusura_auto DATETIME NULL"
                    ))
        
        staff_columns = inspector.get_columns("staff")
        ruolo_column = next((col for col in staff_columns if col["name"] == "ruolo"), None)
        desired_roles = ("admin", "barista", "ingressista")
        legacy_roles = ("staff", "cassa")
        if ruolo_column and not is_sqlite:  # Salta le migrazioni ENUM per SQLite
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
    
    # ⚡ Apertura/Chiusura automatica eventi
    # Chiama la funzione prima di ogni richiesta per controllare gli eventi
    @app.before_request
    def check_auto_eventi():
        from app.utils.auto_eventi import processa_apertura_chiusura_automatica
        # Esegui il controllo (non blocca se c'è un errore)
        try:
            processa_apertura_chiusura_automatica()
        except Exception:
            pass  # Non bloccare le richieste se c'è un errore

    # Context processor per conteggio prenotazioni tavolo in attesa (admin)
    @app.context_processor
    def inject_prenotazioni_tavolo_attesa():
        """Aggiunge il conteggio delle prenotazioni tavolo in attesa a tutte le pagine admin"""
        from flask import session, request
        from app.database import SessionLocal
        from app.models.prenotazioni import Prenotazione
        
        # Solo per pagine admin e se l'utente è admin
        if request.endpoint and request.endpoint.startswith(('prenotazioni.admin_', 'dashboard.admin_', 'eventi.admin_', 'clienti.admin_', 'ingressi.admin_', 'consumi.admin_', 'feedback.admin_', 'staff_admin.', 'prodotti.admin_', 'log.', 'stats.admin_')):
            # Verifica se l'utente è admin
            if session.get('staff_role') == 'admin':
                db = SessionLocal()
                try:
                    count = db.query(Prenotazione).filter(
                        Prenotazione.tipo == "tavolo",
                        Prenotazione.stato_approvazione_tavolo == "in_attesa"
                    ).count()
                    return {'prenotazioni_tavolo_attesa_count': count}
                except Exception:
                    return {'prenotazioni_tavolo_attesa_count': 0}
                finally:
                    db.close()
        
        return {'prenotazioni_tavolo_attesa_count': 0}

    return app