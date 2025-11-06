from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Fedelta(Base):
    __tablename__ = "fedelta"

    id_fedelta = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    punti = Column(Integer, nullable=False)
    motivo = Column(String(200))
    data_assegnazione = Column(DateTime, server_default=func.now())

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="fedelta")
    evento = relationship("Evento", back_populates="fedelta")

    def __repr__(self):
        return f"<Fedelta(id={self.id_fedelta}, cliente_id={self.cliente_id}, punti={self.punti})>"