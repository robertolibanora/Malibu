from sqlalchemy import Column, Integer, Enum
from app.database import Base


class SogliaFedelta(Base):
    __tablename__ = "soglie_fedelta"

    id = Column(Integer, primary_key=True)
    livello = Column(Enum('base','loyal','premium','vip', name='soglia_livello_enum'), unique=True, nullable=False)
    punti_min = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<SogliaFedelta(id={self.id}, livello='{self.livello}', punti_min={self.punti_min})>"

