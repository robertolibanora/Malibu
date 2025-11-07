from sqlalchemy import Column, Integer, String
from app.database import Base


class TemplateEvento(Base):
    __tablename__ = "template_eventi"

    id_template = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    categoria = Column(String(50), nullable=False, default="altro")
    tipo_musica = Column(String(50), nullable=True)
    capienza = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<TemplateEvento(id={self.id_template}, nome='{self.nome}')>"


# Elenco dei template evento usati come fallback per precompilare la creazione
# (usato solo se la tabella è vuota)
TEMPLATE_EVENTI = [
    {
        "nome": "Reggaeton Night",
        "categoria": "reggaeton",
        "tipo_musica": "Reggaeton",
        "capienza": 2500,
    },
    {
        "nome": "Techno Night",
        "categoria": "techno",
        "tipo_musica": "Techno",
        "capienza": 2000,
    },
    {
        "nome": "Private Party",
        "categoria": "privato",
        "tipo_musica": "Mixed",
        "capienza": 1500,
    },
    {
        "nome": "Malibu Saturday",
        "categoria": "altro",
        "tipo_musica": "Commercial/House",
        "capienza": 2500,
    },
]

