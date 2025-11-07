from flask import Flask, redirect, url_for, render_template
from sqlalchemy.orm import sessionmaker
from app.database import engine, Base
from dotenv import load_dotenv
import os
from pathlib import Path
from app.routes import all_blueprints  # ✅ import centralizzato
from app.routes.staff import staff_bp, staff_admin_bp

def create_app():
    load_dotenv()
    # Percorso assoluto alla directory templates e static (relativo alla root del progetto)
    base_dir = Path(__file__).parent.parent
    template_dir = base_dir / 'templates'
    static_dir = base_dir / 'static'
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.secret_key = os.getenv("SECRET_KEY")

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

    # Route root: reindirizza al login
    @app.route("/")
    def root():
        return redirect(url_for("auth.auth_login_form"))

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

    # Registra automaticamente tutti i blueprint
    for bp in all_blueprints:
        app.register_blueprint(bp)

    # Registra blueprint staff
    app.register_blueprint(staff_bp)
    app.register_blueprint(staff_admin_bp)

    return app