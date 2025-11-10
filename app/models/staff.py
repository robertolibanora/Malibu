from sqlalchemy import Column, Integer, String, Enum, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id_staff = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    ruolo = Column(
        Enum("admin", "barista", "ingressista", name="ruolo_enum"),
        nullable=False,
        default="ingressista"
    )
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    attivo = Column(Boolean, default=True)

    # 🔗 Relazioni ORM
    ingressi = relationship("Ingresso", back_populates="staff")
    consumi = relationship("Consumo", back_populates="staff")
    log_attivita = relationship("LogAttivita", back_populates="staff")

    def __repr__(self):
        return f"<Staff(id={self.id_staff}, nome='{self.nome}', ruolo='{self.ruolo}')>"