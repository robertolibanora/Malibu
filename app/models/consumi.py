from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Enum, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Consumo(Base):
    __tablename__ = "consumi"

    id_consumo = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id_staff", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    prodotto_id = Column(Integer, ForeignKey("prodotti.id_prodotto", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    prodotto = Column(String(100), nullable=False)
    importo = Column(DECIMAL(8, 2), nullable=False)
    data_consumo = Column(DateTime, server_default=func.now())
    punto_vendita = Column(Enum("tavolo", "privè", name="punto_vendita_enum"), nullable=False)
    note = Column(Text)

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="consumi")
    evento = relationship("Evento", back_populates="consumi")
    staff = relationship("Staff", back_populates="consumi")
    prodotto_rel = relationship("Prodotto", back_populates="consumi")

    def __repr__(self):
        return f"<Consumo(id={self.id_consumo}, prodotto='{self.prodotto}', importo={self.importo})>"