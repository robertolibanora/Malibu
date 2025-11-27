"""
Servizio per query statistiche aggregate
"""
from sqlalchemy import func, case, and_, or_
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


def get_ingressi_stats(db: Session, evento_id: Optional[int] = None, giorni: int = 30) -> Dict:
    """Statistiche ingressi: totale, trend giornaliero, per ora"""
    from app.models.ingressi import Ingresso
    from app.models.eventi import Evento
    
    base_query = db.query(Ingresso)
    if evento_id:
        base_query = base_query.filter(Ingresso.evento_id == evento_id)
    
    # Totale ingressi
    totale = base_query.count()
    
    # Trend ultimi N giorni
    data_inizio = datetime.now() - timedelta(days=giorni)
    ingressi_giornalieri = db.query(
        func.date(Ingresso.orario_ingresso).label('data'),
        func.count(Ingresso.id_ingresso).label('count')
    ).filter(
        Ingresso.orario_ingresso >= data_inizio
    )
    if evento_id:
        ingressi_giornalieri = ingressi_giornalieri.filter(Ingresso.evento_id == evento_id)
    
    ingressi_giornalieri = ingressi_giornalieri.group_by(
        func.date(Ingresso.orario_ingresso)
    ).order_by('data').all()
    
    trend_data = [{'data': str(row.data), 'count': row.count} for row in ingressi_giornalieri]
    
    # Ingressi per ora (ultimo evento o evento specifico)
    ingressi_per_ora = db.query(
        func.extract('hour', Ingresso.orario_ingresso).label('ora'),
        func.count(Ingresso.id_ingresso).label('count')
    )
    if evento_id:
        ingressi_per_ora = ingressi_per_ora.filter(Ingresso.evento_id == evento_id)
    else:
        # Ultimo evento
        ultimo_evento = db.query(Evento).order_by(Evento.data_evento.desc()).first()
        if ultimo_evento:
            ingressi_per_ora = ingressi_per_ora.filter(Ingresso.evento_id == ultimo_evento.id_evento)
    
    ingressi_per_ora = ingressi_per_ora.group_by(
        func.extract('hour', Ingresso.orario_ingresso)
    ).order_by('ora').all()
    
    ore_data = [{'ora': int(row.ora), 'count': row.count} for row in ingressi_per_ora]
    
    # Saturazione capienza per evento
    saturazione_eventi = []
    eventi_query = db.query(Evento)
    if evento_id:
        eventi_query = eventi_query.filter(Evento.id_evento == evento_id)
    else:
        eventi_query = eventi_query.order_by(Evento.data_evento.desc()).limit(10)
    
    for evento in eventi_query.all():
        ingressi_evento = db.query(func.count(Ingresso.id_ingresso)).filter(
            Ingresso.evento_id == evento.id_evento
        ).scalar() or 0
        
        capienza = evento.capienza_max or 0
        percentuale = (ingressi_evento / capienza * 100) if capienza > 0 else 0
        
        saturazione_eventi.append({
            'evento': evento.nome_evento,
            'ingressi': ingressi_evento,
            'capienza': capienza,
            'percentuale': round(percentuale, 1)
        })
    
    return {
        'totale': totale,
        'trend_giornaliero': trend_data,
        'per_ora': ore_data,
        'saturazione_eventi': saturazione_eventi
    }


def get_prenotazioni_stats(db: Session, evento_id: Optional[int] = None) -> Dict:
    """Statistiche prenotazioni: conversioni, approvazioni tavoli, trend"""
    from app.models.prenotazioni import Prenotazione
    from app.models.eventi import Evento
    
    base_query = db.query(Prenotazione)
    if evento_id:
        base_query = base_query.filter(Prenotazione.evento_id == evento_id)
    
    # Totale prenotazioni
    totale = base_query.count()
    
    # Per tipo
    lista_count = base_query.filter(Prenotazione.tipo == "lista").count()
    tavolo_count = base_query.filter(Prenotazione.tipo == "tavolo").count()
    
    # Stati approvazione tavoli
    tavoli_in_attesa = base_query.filter(
        Prenotazione.tipo == "tavolo",
        Prenotazione.stato_approvazione_tavolo == "in_attesa"
    ).count()
    
    tavoli_approvati = base_query.filter(
        Prenotazione.tipo == "tavolo",
        Prenotazione.stato_approvazione_tavolo == "approvata"
    ).count()
    
    tavoli_rifiutati = base_query.filter(
        Prenotazione.tipo == "tavolo",
        Prenotazione.stato_approvazione_tavolo == "rifiutata"
    ).count()
    
    # Trend mensile (usa evento.data_evento come proxy)
    # Raggruppa per evento e mese dell'evento
    trend_mensile_query = db.query(
        Prenotazione.evento_id,
        func.count(Prenotazione.id_prenotazione).label('count')
    )
    if evento_id:
        trend_mensile_query = trend_mensile_query.filter(Prenotazione.evento_id == evento_id)
    
    trend_mensile_query = trend_mensile_query.group_by(
        Prenotazione.evento_id
    ).all()
    
    # Raggruppa per mese usando data_evento
    mesi_dict = defaultdict(int)
    for row in trend_mensile_query:
        evento = db.query(Evento).get(row.evento_id)
        if evento and evento.data_evento:
            mese = evento.data_evento.strftime('%Y-%m') if hasattr(evento.data_evento, 'strftime') else str(evento.data_evento)[:7]
            mesi_dict[mese] += row.count
    
    trend_data = [{'mese': mese, 'count': count} for mese, count in sorted(mesi_dict.items())]
    
    # Conversioni lista -> tavolo (clienti che hanno fatto entrambi)
    conversioni = db.query(func.count(func.distinct(Prenotazione.cliente_id))).filter(
        Prenotazione.tipo == "tavolo",
        Prenotazione.stato == "attiva"
    )
    if evento_id:
        conversioni = conversioni.filter(Prenotazione.evento_id == evento_id)
    
    conversioni_count = conversioni.scalar() or 0
    
    return {
        'totale': totale,
        'lista': lista_count,
        'tavolo': tavolo_count,
        'tavoli_in_attesa': tavoli_in_attesa,
        'tavoli_approvati': tavoli_approvati,
        'tavoli_rifiutati': tavoli_rifiutati,
        'trend_mensile': trend_data,
        'conversioni': conversioni_count
    }


def get_consumi_stats(db: Session, evento_id: Optional[int] = None) -> Dict:
    """Statistiche consumi: revenue, scontrino medio, top prodotti"""
    from app.models.consumi import Consumo
    from app.models.prodotti import Prodotto
    
    base_query = db.query(Consumo)
    if evento_id:
        base_query = base_query.filter(Consumo.evento_id == evento_id)
    
    # Revenue totale
    revenue_totale = db.query(func.coalesce(func.sum(Consumo.importo), 0)).filter(
        base_query.whereclause if evento_id else True
    ).scalar() or 0
    
    # Numero ordini
    num_ordini = base_query.count()
    
    # Scontrino medio
    scontrino_medio = (revenue_totale / num_ordini) if num_ordini > 0 else 0
    
    # Top prodotti per categoria
    # Nota: Consumo non ha campo quantita, ogni record è un consumo
    # La quantità può essere nel nome prodotto (es. "Cocktail x3")
    top_prodotti = db.query(
        Prodotto.categoria,
        Prodotto.nome,
        Prodotto.id_prodotto,
        func.count(Consumo.id_consumo).label('num_consumi'),
        func.sum(Consumo.importo).label('revenue')
    ).join(
        Consumo, Consumo.prodotto_id == Prodotto.id_prodotto
    )
    if evento_id:
        top_prodotti = top_prodotti.filter(Consumo.evento_id == evento_id)
    
    top_prodotti = top_prodotti.group_by(
        Prodotto.categoria, Prodotto.nome, Prodotto.id_prodotto
    ).order_by(
        func.sum(Consumo.importo).desc()
    ).limit(20).all()
    
    # Calcola quantità totale estraendo dal nome prodotto se presente
    import re
    prodotti_data = []
    for row in top_prodotti:
        # Estrai quantità dal nome prodotto se presente (es. "Cocktail x3" -> 3)
        # Per ogni consumo di questo prodotto, verifica se ha quantità nel nome
        consumi_prodotto = db.query(Consumo.prodotto).filter(
            Consumo.prodotto_id == row.id_prodotto
        )
        if evento_id:
            consumi_prodotto = consumi_prodotto.filter(Consumo.evento_id == evento_id)
        
        quantita_totale = 0
        for consumo_row in consumi_prodotto.all():
            nome_prod = consumo_row.prodotto or ""
            # Cerca pattern " x3" alla fine del nome
            match = re.search(r'\s+x(\d+)$', nome_prod)
            if match:
                quantita_totale += int(match.group(1))
            else:
                quantita_totale += 1  # Default: 1 unità
        
        prodotti_data.append({
            'categoria': row.categoria or 'Altro',
            'nome': row.nome,
            'quantita': quantita_totale if quantita_totale > 0 else int(row.num_consumi),
            'revenue': float(row.revenue)
        })
    
    # Revenue per categoria
    revenue_categoria = db.query(
        Prodotto.categoria,
        func.sum(Consumo.importo).label('revenue')
    ).join(
        Consumo, Consumo.prodotto_id == Prodotto.id_prodotto
    )
    if evento_id:
        revenue_categoria = revenue_categoria.filter(Consumo.evento_id == evento_id)
    
    revenue_categoria = revenue_categoria.group_by(
        Prodotto.categoria
    ).order_by(
        func.sum(Consumo.importo).desc()
    ).all()
    
    categorie_data = [
        {'categoria': row.categoria or 'Altro', 'revenue': float(row.revenue)}
        for row in revenue_categoria
    ]
    
    # Trend giornaliero revenue
    data_inizio = datetime.now() - timedelta(days=30)
    trend_revenue = db.query(
        func.date(Consumo.data_consumo).label('data'),
        func.sum(Consumo.importo).label('revenue')
    ).filter(
        Consumo.data_consumo >= data_inizio
    )
    if evento_id:
        trend_revenue = trend_revenue.filter(Consumo.evento_id == evento_id)
    
    trend_revenue = trend_revenue.group_by(
        func.date(Consumo.data_consumo)
    ).order_by('data').all()
    
    revenue_trend = [
        {'data': str(row.data), 'revenue': float(row.revenue)}
        for row in trend_revenue
    ]
    
    return {
        'revenue_totale': float(revenue_totale),
        'num_ordini': num_ordini,
        'scontrino_medio': round(scontrino_medio, 2),
        'top_prodotti': prodotti_data,
        'revenue_per_categoria': categorie_data,
        'trend_revenue': revenue_trend
    }


def get_clienti_stats(db: Session) -> Dict:
    """Statistiche clienti: distribuzione livelli, retention, nuovi"""
    from app.models.clienti import Cliente
    from app.models.eventi import Evento
    
    # Totale clienti
    totale_clienti = db.query(func.count(Cliente.id_cliente)).scalar() or 0
    
    # Distribuzione livelli fedeltà
    livelli = db.query(
        Cliente.livello,
        func.count(Cliente.id_cliente).label('count')
    ).group_by(
        Cliente.livello
    ).all()
    
    distribuzione_livelli = {
        row.livello: row.count for row in livelli
    }
    
    # Nuovi clienti ultimi 30 giorni
    data_inizio = datetime.now() - timedelta(days=30)
    nuovi_clienti = db.query(func.count(Cliente.id_cliente)).filter(
        Cliente.data_registrazione >= data_inizio
    ).scalar() or 0
    
    # Clienti attivi (con almeno una prenotazione negli ultimi 90 giorni)
    from app.models.prenotazioni import Prenotazione
    data_attivita = datetime.now().date() - timedelta(days=90)
    clienti_attivi = db.query(func.count(func.distinct(Prenotazione.cliente_id)))\
        .join(Evento, Prenotazione.evento_id == Evento.id_evento)\
        .filter(
            Evento.data_evento.isnot(None),
            Evento.data_evento >= data_attivita
        ).scalar() or 0
    
    return {
        'totale': totale_clienti,
        'distribuzione_livelli': distribuzione_livelli,
        'nuovi_ultimi_30_giorni': nuovi_clienti,
        'attivi_ultimi_90_giorni': clienti_attivi
    }


def get_overview_stats(db: Session, evento_id: Optional[int] = None) -> Dict:
    """Statistiche overview: KPI principali"""
    ingressi_stats = get_ingressi_stats(db, evento_id, giorni=7)
    prenotazioni_stats = get_prenotazioni_stats(db, evento_id)
    consumi_stats = get_consumi_stats(db, evento_id)
    clienti_stats = get_clienti_stats(db)
    
    return {
        'ingressi': {
            'totale': ingressi_stats['totale'],
            'ultimi_7_giorni': sum(d['count'] for d in ingressi_stats['trend_giornaliero'])
        },
        'prenotazioni': {
            'totale': prenotazioni_stats['totale'],
            'tavoli_in_attesa': prenotazioni_stats['tavoli_in_attesa'],
            'conversioni': prenotazioni_stats['conversioni']
        },
        'consumi': {
            'revenue_totale': consumi_stats['revenue_totale'],
            'scontrino_medio': consumi_stats['scontrino_medio'],
            'num_ordini': consumi_stats['num_ordini']
        },
        'clienti': {
            'totale': clienti_stats['totale'],
            'nuovi_30_giorni': clienti_stats['nuovi_ultimi_30_giorni'],
            'attivi_90_giorni': clienti_stats['attivi_ultimi_90_giorni']
        }
    }

