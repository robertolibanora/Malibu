from sqlalchemy import Column, Integer, Enum, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Ingresso(Base):
    __tablename__ = "ingressi"

    id_ingresso = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    prenotazione_id = Column(Integer, ForeignKey("prenotazioni.id_prenotazione", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id_staff", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    tipo_ingresso = Column(Enum("lista", "tavolo", "omaggio", "prevendita", name="tipo_ingresso_enum"), nullable=False)
    orario_ingresso = Column(DateTime, server_default=func.now())
    note = Column(Text)

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="ingressi")
    evento = relationship("Evento", back_populates="ingressi")
    prenotazione = relationship("Prenotazione", back_populates="ingressi")
    staff = relationship("Staff", back_populates="ingressi")

    def __repr__(self):
        return f"<Ingresso(id={self.id_ingresso}, tipo='{self.tipo_ingresso}', evento_id={self.evento_id})>"