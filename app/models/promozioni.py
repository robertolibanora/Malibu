from sqlalchemy import Column, Integer, String, Text, DECIMAL, Boolean, Date, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Promozione(Base):
    __tablename__ = "promozioni"

    id_promozione = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    descrizione = Column(Text)
    tipo = Column(
        Enum("sconto_percentuale", "sconto_fisso", "omaggio", "ingresso_gratis", "consumo_gratis", "altro", name="tipo_promozione_enum"),
        nullable=False,
        default="altro"
    )
    valore = Column(DECIMAL(8, 2), nullable=True)  # percentuale o importo fisso
    condizioni = Column(Text)  # condizioni per ottenere la promozione
    attiva = Column(Boolean, default=True)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    livello_richiesto = Column(
        Enum("base", "loyal", "premium", "vip", name="livello_enum"),
        nullable=True
    )
    punti_richiesti = Column(Integer, nullable=True)
    auto_assegnazione = Column(Boolean, default=False)  # assegnazione automatica alla registrazione

    # 🔗 Relazioni ORM
    clienti_promozioni = relationship("ClientePromozione", back_populates="promozione", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Promozione(id={self.id_promozione}, nome='{self.nome}', tipo='{self.tipo}')>"


class ClientePromozione(Base):
    __tablename__ = "clienti_promozioni"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clienti.id_cliente", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    promozione_id = Column(Integer, ForeignKey("promozioni.id_promozione", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    data_assegnazione = Column(DateTime, server_default=func.now())
    data_scadenza = Column(Date, nullable=True)
    usata = Column(Boolean, default=False)
    data_uso = Column(DateTime, nullable=True)
    note = Column(Text)

    # 🔗 Relazioni ORM
    cliente = relationship("Cliente", back_populates="promozioni")
    promozione = relationship("Promozione", back_populates="clienti_promozioni")

    def __repr__(self):
        return f"<ClientePromozione(cliente_id={self.cliente_id}, promozione_id={self.promozione_id}, usata={self.usata})>"

