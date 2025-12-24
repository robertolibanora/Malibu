from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# Carica le variabili dal file .env
load_dotenv()

# Recupera i valori dal file .env
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")
USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() == "true"

# Se USE_SQLITE è true, usa SQLite per lo sviluppo locale
if USE_SQLITE:
    from pathlib import Path
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / "malibu.db"
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
else:
    # Usa MySQL come di default
    SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Connessione
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    """
    Context manager per sessioni database.
    
    Uso:
        with get_db() as db:
            result = db.query(Model).all()
            # La sessione viene chiusa automaticamente
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()