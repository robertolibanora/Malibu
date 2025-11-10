from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ConfigApp(Base):
    __tablename__ = "config_app"

    chiave = Column(String(50), primary_key=True)
    valore = Column(String(255), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ConfigApp(key='{self.chiave}', value='{self.valore}')>"


