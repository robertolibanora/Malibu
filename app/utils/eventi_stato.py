"""
Utility centralizzata per gestire i cambi di stato degli eventi
"""
from app.database import SessionLocal
from app.models.eventi import Evento
from app.utils.events import set_evento_operativo_id, get_evento_operativo_id
from app.routes.log_attivita import log_action


def imposta_stato_evento(db, evento: Evento, nuovo_stato: str, staff_id=None, automatico=False):
    """
    Imposta lo stato di un evento e gestisce automaticamente staff operativo e pubblico.
    
    Stati:
    - "programmato": Evento visibile, prenotazioni aperte, staff non operativo
    - "attivo": Evento attivo, staff operativo automaticamente, pubblico attivo
    - "chiuso": Evento chiuso, staff disattivato, pubblico chiuso, visibile solo in passati
    
    Args:
        db: Sessione database
        evento: Istanza Evento
        nuovo_stato: "programmato", "attivo" o "chiuso"
        staff_id: ID staff che esegue l'azione (None se automatico)
        automatico: True se è un cambio automatico
    
    Returns:
        bool: True se il cambio è stato applicato, False altrimenti
    """
    if nuovo_stato not in ("programmato", "attivo", "chiuso"):
        return False
    
    if evento.stato_pubblico == nuovo_stato:
        return False  # Già nello stato richiesto
    
    vecchio_stato = evento.stato_pubblico
    evento.stato_pubblico = nuovo_stato
    
    if nuovo_stato == "attivo":
        # Quando diventa attivo: attiva staff operativo e pubblico automaticamente
        evento.is_staff_operativo = True
        # Imposta come evento operativo (sostituisce eventuale altro evento operativo)
        set_evento_operativo_id(db, evento.id_evento)
        
        azione = "auto_activate" if automatico else "manual_activate"
        note = f"Evento attivato (da {vecchio_stato} a attivo)"
        if automatico:
            note += f" - Apertura automatica"
    
    elif nuovo_stato == "chiuso":
        # Quando diventa chiuso: disattiva staff operativo
        evento.is_staff_operativo = False
        # Se era l'evento operativo, disattivalo
        evento_operativo_id = get_evento_operativo_id(db)
        if evento_operativo_id == evento.id_evento:
            set_evento_operativo_id(db, None)
        
        azione = "auto_close" if automatico else "manual_close"
        note = f"Evento chiuso (da {vecchio_stato} a chiuso)"
        if automatico:
            note += f" - Chiusura automatica"
    
    else:  # programmato
        # Quando torna programmato: disattiva staff operativo
        evento.is_staff_operativo = False
        # Se era l'evento operativo, disattivalo
        evento_operativo_id = get_evento_operativo_id(db)
        if evento_operativo_id == evento.id_evento:
            set_evento_operativo_id(db, None)
        
        azione = "manual_set_programmato" if not automatico else "auto_set_programmato"
        note = f"Evento impostato a programmato (da {vecchio_stato} a programmato)"
    
    # Log dell'azione
    log_action(
        db,
        tabella="eventi",
        record_id=evento.id_evento,
        staff_id=staff_id,
        azione=azione,
        note=note
    )
    
    return True


