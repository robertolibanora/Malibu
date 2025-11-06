from sqlalchemy import Column, Integer, String, DECIMAL, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Prodotto(Base):
    __tablename__ = "prodotti"

    id_prodotto = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    prezzo = Column(DECIMAL(8, 2), nullable=False)
    categoria = Column(String(50), nullable=True)
    attivo = Column(Boolean, default=True)

    # 🔗 Relazioni ORM
    consumi = relationship("Consumo", back_populates="prodotto_rel")

    def __repr__(self):
        return f"<Prodotto(id={self.id_prodotto}, nome='{self.nome}', prezzo={self.prezzo})>"

