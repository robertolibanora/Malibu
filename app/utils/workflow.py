"""
📋 Workflow Helpers — Logica lineare del flusso EVENTO → PRENOTAZIONE → INGRESSO → FEEDBACK/CONSUMI

Questo modulo centralizza tutte le verifiche per garantire coerenza nel flusso utente
e bloccare azioni incoerenti. È la fonte unica di verità per le condizioni di accesso.
"""

from datetime import datetime, time, date
from sqlalchemy import and_
from app.models.prenotazioni import Prenotazione
from app.models.ingressi import Ingresso
from app.models.feedback import Feedback
from app.models.consumi import Consumo
from app.models.eventi import Evento


class WorkflowState:
    """
    Stato aggregato di un cliente rispetto a un evento.
    Determina quali azioni sono permesse nel flusso.
    """
    def __init__(self, cliente_id: int, evento_id: int, db):
        self.cliente_id = cliente_id
        self.evento_id = evento_id
        self.db = db
        
        # Cache
        self._evento = None
        self._prenotazione = None
        self._ingresso = None
        self._feedback = None
        self._consumi = None
        
    @property
    def evento(self) -> Evento:
        if self._evento is None:
            self._evento = self.db.query(Evento).get(self.evento_id)
        return self._evento
    
    @property
    def prenotazione_attiva(self) -> Prenotazione:
        """La prenotazione attiva (se esiste) per questo cliente/evento."""
        if self._prenotazione is None:
            self._prenotazione = self.db.query(Prenotazione).filter(
                Prenotazione.cliente_id == self.cliente_id,
                Prenotazione.evento_id == self.evento_id,
                Prenotazione.stato == "attiva"
            ).first()
        return self._prenotazione
    
    @property
    def ingresso_registrato(self) -> Ingresso:
        """L'ingresso registrato (se esiste) per questo cliente/evento."""
        if self._ingresso is None:
            self._ingresso = self.db.query(Ingresso).filter(
                Ingresso.cliente_id == self.cliente_id,
                Ingresso.evento_id == self.evento_id
            ).first()
        return self._ingresso
    
    @property
    def feedback_lasciato(self) -> Feedback:
        """Il feedback (se esiste) lasciato da questo cliente per questo evento."""
        if self._feedback is None:
            self._feedback = self.db.query(Feedback).filter(
                Feedback.cliente_id == self.cliente_id,
                Feedback.evento_id == self.evento_id
            ).first()
        return self._feedback
    
    @property
    def consumi(self) -> list:
        """Consumi registrati per questo cliente/evento."""
        if self._consumi is None:
            self._consumi = self.db.query(Consumo).filter(
                Consumo.cliente_id == self.cliente_id,
                Consumo.evento_id == self.evento_id
            ).all()
        return self._consumi
    
    # ─────────────────────────────────────────
    # VERIFICHE WORKFLOW
    # ─────────────────────────────────────────
    
    def evento_visibile_cliente(self) -> bool:
        """L'evento è visibile al cliente (non chiuso)?"""
        return self.evento and self.evento.stato_pubblico in ("programmato", "attivo")
    
    def cliente_puo_prenotare(self) -> bool:
        """Il cliente può ancora prenotare? (nessuna prenotazione attiva, evento aperto)"""
        if not self.evento_visibile_cliente():
            return False
        return self.prenotazione_attiva is None
    
    def cliente_puo_cancellare_prenotazione(self) -> bool:
        """Il cliente può cancellare la sua prenotazione? (entro le 18:00 del giorno evento)"""
        if self.prenotazione_attiva is None:
            return False
        if not self.evento:
            return False
        
        cutoff = datetime.combine(self.evento.data_evento, time(18, 0))
        now = datetime.now()
        return now <= cutoff
    
    def cliente_ha_ingresso_valido(self) -> bool:
        """Il cliente è entrato? (ingresso registrato = 'show')"""
        return self.ingresso_registrato is not None
    
    def cliente_puo_registrare_consumi(self) -> bool:
        """Il cliente può registrare consumi? (deve aver avuto ingresso)"""
        return self.cliente_ha_ingresso_valido()
    
    def cliente_puo_lasciare_feedback(self) -> bool:
        """Il cliente può lasciare feedback? (deve aver avuto ingresso + non ha già feedback)"""
        return (
            self.cliente_ha_ingresso_valido() and
            self.feedback_lasciato is None
        )
    
    def cliente_ha_feedback(self) -> bool:
        """Il cliente ha già lasciato feedback?"""
        return self.feedback_lasciato is not None
    
    # ─────────────────────────────────────────
    # INFO UI
    # ─────────────────────────────────────────
    
    def stato_prenotazione_badge(self) -> dict:
        """
        Ritorna info per visualizzare lo stato prenotazione in UI.
        {'label': str, 'class': str, 'color': str}
        """
        if not self.prenotazione_attiva:
            return {"label": "Nessuna prenotazione", "class": "badge-muted", "color": "gray"}
        
        if self.prenotazione_attiva.stato == "attiva":
            return {"label": "✓ Prenotazione attiva", "class": "badge-success", "color": "gold"}
        elif self.prenotazione_attiva.stato == "usata":
            return {"label": "✓ Usata (ingresso valido)", "class": "badge-success", "color": "gold"}
        elif self.prenotazione_attiva.stato == "no-show":
            return {"label": "✗ No-show (penalità −5 pt)", "class": "badge-danger", "color": "black"}
        elif self.prenotazione_attiva.stato == "cancellata":
            return {"label": "Cancellata", "class": "badge-muted", "color": "gray"}
        
        return {"label": "Stato sconosciuto", "class": "badge-muted", "color": "gray"}
    
    def stato_ingresso_badge(self) -> dict:
        """Badge per mostrare se il cliente è entrato."""
        if self.ingresso_registrato:
            return {"label": "✓ Entrato", "class": "badge-success", "color": "gold"}
        return {"label": "Ancora non entrato", "class": "badge-muted", "color": "gray"}
    
    def step_progress(self) -> dict:
        """
        Ritorna lo stato di avanzamento del flusso.
        {
            'step_1_evento': {'completed': bool, 'label': 'Evento'},
            'step_2_prenotazione': {...},
            'step_3_ingresso': {...},
            'step_4_feedback': {...},
            'step_5_consumi': {...}
        }
        """
        evento_ok = self.evento_visibile_cliente()
        pren_ok = self.prenotazione_attiva is not None
        ingresso_ok = self.ingresso_registrato is not None
        feedback_ok = self.feedback_lasciato is not None
        consumi_ok = len(self.consumi) > 0
        
        return {
            "step_1_evento": {
                "label": "📅 Evento",
                "completed": evento_ok,
                "enabled": evento_ok,
                "description": "Scegli l'evento"
            },
            "step_2_prenotazione": {
                "label": "🎟️ Prenotazione",
                "completed": pren_ok,
                "enabled": evento_ok,
                "description": "Prenota il tuo posto" if evento_ok else "Scegli un evento first",
                "current": pren_ok
            },
            "step_3_ingresso": {
                "label": "🚪 Ingresso",
                "completed": ingresso_ok,
                "enabled": pren_ok,
                "description": "Entra all'evento" if pren_ok else "Completa la prenotazione first",
                "current": pren_ok and not ingresso_ok
            },
            "step_4_feedback": {
                "label": "⭐ Feedback",
                "completed": feedback_ok,
                "enabled": ingresso_ok,
                "description": "Lascia una recensione" if ingresso_ok else "Devi entrare first",
                "current": ingresso_ok and not feedback_ok
            },
            "step_5_consumi": {
                "label": "🍾 Consumi",
                "completed": consumi_ok,
                "enabled": ingresso_ok,
                "description": "I tuoi acquisti" if ingresso_ok else "Devi entrare first",
                "current": ingresso_ok and not consumi_ok
            }
        }


def get_workflow_state(db, cliente_id: int, evento_id: int) -> WorkflowState:
    """Ottiene lo stato aggregato del flusso per un cliente e un evento."""
    return WorkflowState(cliente_id, evento_id, db)


def can_cliente_see_feedback_button(db, cliente_id: int, evento_id: int) -> bool:
    """Dovrebbe mostrare il bottone 'Lascia feedback'?"""
    state = get_workflow_state(db, cliente_id, evento_id)
    return state.cliente_puo_lasciare_feedback()


def can_cliente_see_consumi_section(db, cliente_id: int, evento_id: int) -> bool:
    """Dovrebbe mostrare la sezione consumi?"""
    state = get_workflow_state(db, cliente_id, evento_id)
    return state.cliente_ha_ingresso_valido()


def evento_stato_badge(evento: Evento) -> dict:
    """
    Badge per visualizzare lo stato dell'evento in UI.
    Uso colori: ORO = attivo, NERO = chiuso, GRIGIO = programmato
    """
    if evento.stato_pubblico == "attivo":
        return {
            "label": "● ATTIVO ADESSO",
            "class": "badge-active",
            "color": "gold",
            "icon": "🔴"
        }
    elif evento.stato_pubblico == "programmato":
        return {
            "label": "● Programmato",
            "class": "badge-scheduled",
            "color": "gray",
            "icon": "⏱️"
        }
    elif evento.stato_pubblico == "chiuso":
        return {
            "label": "● Chiuso",
            "class": "badge-closed",
            "color": "black",
            "icon": "⏹️"
        }
    
    return {"label": "● Sconosciuto", "class": "badge-muted", "color": "gray", "icon": "?"}

