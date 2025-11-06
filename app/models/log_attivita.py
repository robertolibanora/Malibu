from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class LogAttivita(Base):
    __tablename__ = "log_attivita"

    id_log = Column(Integer, primary_key=True, index=True)
    tabella = Column(String(50), nullable=False)
    record_id = Column(Integer, nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id_staff", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    azione = Column(Enum("insert", "update", "delete", name="azione_enum"), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    # 🔗 Relazioni ORM
    staff = relationship("Staff", back_populates="log_attivita")

    def __repr__(self):
        return f"<LogAttivita(id={self.id_log}, tabella='{self.tabella}', azione='{self.azione}')>"