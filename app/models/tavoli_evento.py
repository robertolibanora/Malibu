"""
Modello per gestire i tavoli disponibili per evento
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from app.database import Base


class TavoloEvento(Base):
    """Tavolo configurato dall'admin per un evento specifico"""
    __tablename__ = "tavoli_evento"

    id_tavolo = Column(Integer, primary_key=True, index=True)
    evento_id = Column(Integer, ForeignKey("eventi.id_evento", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    numero_tavolo = Column(Integer, nullable=False)  # Numero fisico del tavolo
    nome_tavolo = Column(String(100))  # Nome descrittivo opzionale (es: "Tavolo VIP 1")
    capienza = Column(Integer, default=4)  # Capienza massima del tavolo
    prezzo_minimo = Column(Integer, default=None)  # Prezzo minimo consumo opzionale
    attivo = Column(Boolean, default=True, nullable=False)  # Se il tavolo è disponibile per prenotazioni
    
    # 🔗 Relazioni
    evento = relationship("Evento", back_populates="tavoli_evento")
    prenotazioni = relationship("Prenotazione", back_populates="tavolo_evento")

    def __repr__(self):
        return f"<TavoloEvento(id={self.id_tavolo}, evento_id={self.evento_id}, numero={self.numero_tavolo})>"

