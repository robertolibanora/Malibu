from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Cliente(Base):
    __tablename__ = "clienti"

    id_cliente = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False)
    cognome = Column(String(50), nullable=False)
    data_nascita = Column(Date)
    citta = Column(String(100))
    telefono = Column(String(20), unique=True)
    password_hash = Column(String(255), nullable=False)
    data_registrazione = Column(DateTime, server_default=func.now())
    ultimo_accesso = Column(DateTime)
    qr_code = Column(String(255), unique=True)
    livello = Column(
        Enum("base", "loyal", "premium", "vip", name="livello_enum"),
        default="base"
    )
    punti_fedelta = Column(Integer, default=0)
    stato_account = Column(
        Enum("attivo", "disattivato", name="stato_account_enum"),
        nullable=False,
        default="attivo"
    )
    nota_staff = Column(Text, nullable=True)

    # 🔗 Relazioni ORM (back_populates definite nei moduli collegati)
    prenotazioni = relationship("Prenotazione", back_populates="cliente", cascade="all, delete-orphan")
    ingressi = relationship("Ingresso", back_populates="cliente", cascade="all, delete-orphan")
    consumi = relationship("Consumo", back_populates="cliente", cascade="all, delete-orphan")
    fedelta = relationship("Fedelta", back_populates="cliente", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="cliente", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cliente(id={self.id_cliente}, nome='{self.nome}', cognome='{self.cognome}')>"