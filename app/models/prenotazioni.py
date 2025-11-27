from sqlalchemy import Column, Integer, Enum, ForeignKey, Text, Time, String
from sqlalchemy.orm import relationship, backref
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
    ruolo_tavolo = Column(
        Enum("referente", "aderente", "none", name="ruolo_tavolo_enum"),
        default="none",
        nullable=False
    )
    prenotazione_padre_id = Column(
        Integer,
        ForeignKey("prenotazioni.id_prenotazione", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True
    )
    codice_invito = Column(String(10), unique=True)
    
    # Campi per prenotazione tavolo
    numero_tavolo = Column(Integer, ForeignKey("tavoli_evento.id_tavolo", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    nome_tavolo_gruppo = Column(String(100))  # Nome del gruppo/tavolo scelto dal cliente
    stato_approvazione_tavolo = Column(
        Enum("in_attesa", "approvata", "rifiutata", name="stato_approvazione_tavolo_enum"),
        default=None,
        nullable=True
    )

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="prenotazioni")
    evento = relationship("Evento", back_populates="prenotazioni")
    ingressi = relationship("Ingresso", back_populates="prenotazione", cascade="all, delete-orphan")
    tavolo_evento = relationship("TavoloEvento", foreign_keys=[numero_tavolo], back_populates="prenotazioni")
    prenotazione_padre = relationship(
        "Prenotazione",
        remote_side=[id_prenotazione],
        backref=backref("aderenti", cascade="all, delete-orphan"),
        foreign_keys=[prenotazione_padre_id]
    )

    def __repr__(self):
        return f"<Prenotazione(id={self.id_prenotazione}, tipo='{self.tipo}', stato='{self.stato}')>"