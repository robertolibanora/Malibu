"""
Utility per gestire l'apertura e chiusura automatica degli eventi
"""
from datetime import datetime
from app.database import SessionLocal
from app.models.eventi import Evento
from app.utils.eventi_stato import imposta_stato_evento


def processa_apertura_chiusura_automatica():
    """
    Controlla gli eventi e li apre/chiude automaticamente in base agli orari impostati.
    Viene chiamata periodicamente per aggiornare lo stato degli eventi.
    """
    db = SessionLocal()
    try:
        now = datetime.now()
        count_aperti = 0
        count_chiusi = 0
        
        # Eventi da aprire (data_ora_apertura_auto <= now e stato ancora "programmato")
        eventi_da_aprire = db.query(Evento).filter(
            Evento.data_ora_apertura_auto.isnot(None),
            Evento.data_ora_apertura_auto <= now,
            Evento.stato_pubblico == "programmato"
        ).all()
        
        for evento in eventi_da_aprire:
            if imposta_stato_evento(db, evento, "attivo", staff_id=None, automatico=True):
                count_aperti += 1
        
        # Eventi da chiudere (data_ora_chiusura_auto <= now e stato ancora "attivo" o "programmato")
        eventi_da_chiudere = db.query(Evento).filter(
            Evento.data_ora_chiusura_auto.isnot(None),
            Evento.data_ora_chiusura_auto <= now,
            Evento.stato_pubblico.in_(["programmato", "attivo"])
        ).all()
        
        for evento in eventi_da_chiudere:
            if imposta_stato_evento(db, evento, "chiuso", staff_id=None, automatico=True):
                count_chiusi += 1
        
        if count_aperti > 0 or count_chiusi > 0:
            db.commit()
            return count_aperti, count_chiusi
        
        return 0, 0
    except Exception as e:
        db.rollback()
        # Log dell'errore ma non bloccare l'applicazione
        print(f"Errore nel processamento automatico eventi: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0
    finally:
        db.close()

