from typing import Optional
from sqlalchemy.orm import Session
from flask import current_app
from app.models.eventi import Evento
from app.models.config_app import ConfigApp


EVENTO_OPERATIVO_KEY = "EVENTO_OPERATIVO_ID"


def get_config_value(db: Session, key: str) -> Optional[str]:
    row = db.query(ConfigApp).get(key)
    return row.valore if row else None


def set_config_value(db: Session, key: str, value: Optional[str]) -> None:
    row = db.query(ConfigApp).get(key)
    if not row:
        row = ConfigApp(chiave=key, valore=value)
        db.add(row)
    else:
        row.valore = value
    db.commit()


def get_evento_operativo_id(db: Session) -> Optional[int]:
    """
    Fonte unica per l'evento operativo staff.
    Non usa più current_app.config: leggiamo da tabella config_app.
    """
    val = get_config_value(db, EVENTO_OPERATIVO_KEY)
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def set_evento_operativo_id(db: Session, evento_id: Optional[int]) -> None:
    set_config_value(db, EVENTO_OPERATIVO_KEY, str(evento_id) if evento_id is not None else None)


def get_evento_operativo(db: Session) -> Optional[Evento]:
    """
    Ritorna l'evento operativo staff se coerente (flag su evento e non chiuso).
    """
    eid = get_evento_operativo_id(db)
    if not eid:
        return None
    ev = db.query(Evento).get(eid)
    if not ev:
        return None
    if not ev.is_staff_operativo:
        return None
    if ev.stato_pubblico == "chiuso":
        return None
    return ev


