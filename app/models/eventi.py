from sqlalchemy import Column, Integer, String, Date, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class Evento(Base):
    __tablename__ = "eventi"

    id_evento = Column(Integer, primary_key=True, index=True)
    nome_evento = Column(String(100), nullable=False)
    data_evento = Column(Date, nullable=False)
    tipo_musica = Column(String(50))
    dj_artista = Column(String(100))
    promozione = Column(String(200))
    capienza_max = Column(Integer, default=2500)
    categoria = Column(
        Enum("reggaeton", "techno", "privato", "altro", name="categoria_enum"),
        default="altro"
    )
    stato = Column(
        Enum("attivo", "chiuso", name="stato_evento_enum"),
        default="attivo"
    )
    cover_url = Column(String(255))  # opzionale: URL immagine di copertina

    # 🔗 Relazioni ORM (verso le altre tabelle)
    prenotazioni = relationship("Prenotazione", back_populates="evento", cascade="all, delete-orphan")
    ingressi = relationship("Ingresso", back_populates="evento", cascade="all, delete-orphan")
    consumi = relationship("Consumo", back_populates="evento", cascade="all, delete-orphan")
    fedelta = relationship("Fedelta", back_populates="evento", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="evento", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Evento(id={self.id_evento}, nome='{self.nome_evento}', data={self.data_evento})>"