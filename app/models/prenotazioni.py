from sqlalchemy import Column, Integer, Enum, ForeignKey, Text, Time
from sqlalchemy.orm import relationship
from app.database import Base


class Prenotazione(Base):
    __tablename__ = "prenotazioni"

    id_prenotazione = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    tipo = Column(Enum("lista", "tavolo", "prevendita", name="tipo_prenotazione_enum"), nullable=False)
    num_persone = Column(Integer, default=None)
    orario_previsto = Column(Time, default=None)
    note = Column(Text)
    stato = Column(Enum("attiva", "no-show", "usata", "cancellata", name="stato_prenotazione_enum"), default="attiva")

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="prenotazioni")
    evento = relationship("Evento", back_populates="prenotazioni")
    ingressi = relationship("Ingresso", back_populates="prenotazione", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prenotazione(id={self.id_prenotazione}, tipo='{self.tipo}', stato='{self.stato}')>"