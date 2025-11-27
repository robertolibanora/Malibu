"""
Helper centralizzati per MalibuApp.

Questo modulo raccoglie tutte le funzioni helper comuni usate nelle route,
eliminando duplicazioni e garantendo consistenza.
"""
from flask import session
from app.database import SessionLocal
from app.models.clienti import Cliente
from app.models.eventi import Evento
from app.models.ingressi import Ingresso


# ─────────────────────────────────────────
# CLIENTE HELPERS
# ─────────────────────────────────────────

def get_current_cliente_id() -> int | None:
    """Ottiene l'ID del cliente dalla sessione."""
    return session.get("cliente_id")


def get_current_cliente(db) -> Cliente | None:
    """
    Ottiene il cliente attualmente loggato dalla sessione.
    
    Args:
        db: Sessione database attiva
        
    Returns:
        Cliente o None se non loggato
    """
    cid = get_current_cliente_id()
    if not cid:
        return None
    return db.query(Cliente).get(cid)


def get_cliente_by_qr(db, qr: str) -> Cliente | None:
    """
    Cerca un cliente tramite QR code.
    
    Args:
        db: Sessione database attiva
        qr: Codice QR del cliente
        
    Returns:
        Cliente o None se non trovato
    """
    if not qr:
        return None
    return db.query(Cliente).filter(Cliente.qr_code == qr.strip()).first()


def cliente_has_ingresso(db, cliente_id: int, evento_id: int) -> bool:
    """
    Verifica se un cliente ha un ingresso registrato per un evento.
    
    Args:
        db: Sessione database attiva
        cliente_id: ID del cliente
        evento_id: ID dell'evento
        
    Returns:
        True se ha ingresso, False altrimenti
    """
    return db.query(Ingresso.id_ingresso).filter(
        Ingresso.cliente_id == cliente_id,
        Ingresso.evento_id == evento_id
    ).first() is not None


# ─────────────────────────────────────────
# STAFF HELPERS
# ─────────────────────────────────────────

def get_current_staff_id() -> int | None:
    """Ottiene l'ID dello staff dalla sessione."""
    return session.get("staff_id")


def get_current_staff_role() -> str | None:
    """Ottiene il ruolo dello staff dalla sessione."""
    return session.get("staff_role")


def is_staff_admin() -> bool:
    """Verifica se l'utente corrente è admin."""
    return get_current_staff_role() == "admin"


def is_staff_operative() -> bool:
    """Verifica se l'utente corrente ha un ruolo operativo (ingressista/barista)."""
    return get_current_staff_role() in ("ingressista", "barista")


# ─────────────────────────────────────────
# EVENTO HELPERS (wrapper per compatibilità)
# ─────────────────────────────────────────

def get_evento_attivo(db) -> Evento | None:
    """
    Ottiene l'evento operativo attivo.
    Wrapper per get_evento_operativo per retrocompatibilità.
    
    Args:
        db: Sessione database attiva
        
    Returns:
        Evento o None
    """
    from app.utils.events import get_evento_operativo
    return get_evento_operativo(db)

