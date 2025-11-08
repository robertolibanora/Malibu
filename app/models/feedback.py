from sqlalchemy import Column, Integer, SmallInteger, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id_feedback = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    voto_musica = Column(SmallInteger, nullable=False)
    voto_ingresso = Column(SmallInteger, nullable=False)
    voto_ambiente = Column(SmallInteger, nullable=False)
    voto_servizio = Column(SmallInteger, nullable=False, default=5)
    data_feedback = Column(DateTime, server_default=func.now())
    note = Column(Text)

    # 🔒 vincoli di validazione locale
    __table_args__ = (
        CheckConstraint("voto_musica BETWEEN 1 AND 10", name="chk_voto_musica"),
        CheckConstraint("voto_ingresso BETWEEN 1 AND 10", name="chk_voto_ingresso"),
        CheckConstraint("voto_ambiente BETWEEN 1 AND 10", name="chk_voto_ambiente"),
        CheckConstraint("voto_servizio BETWEEN 1 AND 10", name="chk_voto_servizio"),
    )

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="feedback")
    evento = relationship("Evento", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback(id={self.id_feedback}, cliente_id={self.cliente_id}, evento_id={self.evento_id})>"