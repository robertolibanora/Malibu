"""
Blueprint per le statistiche admin
"""
from flask import Blueprint, render_template, request, session
from app.database import SessionLocal
from app.models.eventi import Evento
from app.utils.decorators import require_admin
from app.services.statistics import (
    get_overview_stats,
    get_ingressi_stats,
    get_prenotazioni_stats,
    get_consumi_stats,
    get_clienti_stats
)

stats_bp = Blueprint("stats", __name__, url_prefix="/admin/stats")


@stats_bp.route("/")
@require_admin
def admin_hub():
    """Hub statistiche - Overview generale"""
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        
        # Lista eventi per filtro
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        
        # Statistiche overview
        stats = get_overview_stats(db, evento_id)
        
        return render_template(
            "admin/stats_hub.html",
            stats=stats,
            eventi=eventi,
            evento_selezionato_id=evento_id
        )
    finally:
        db.close()


@stats_bp.route("/overview")
@require_admin
def admin_overview():
    """Statistiche overview dettagliate"""
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        giorni = request.args.get("giorni", type=int, default=30)
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        
        # Statistiche complete
        ingressi_stats = get_ingressi_stats(db, evento_id, giorni)
        prenotazioni_stats = get_prenotazioni_stats(db, evento_id)
        consumi_stats = get_consumi_stats(db, evento_id)
        clienti_stats = get_clienti_stats(db)
        
        return render_template(
            "admin/stats_overview.html",
            ingressi_stats=ingressi_stats,
            prenotazioni_stats=prenotazioni_stats,
            consumi_stats=consumi_stats,
            clienti_stats=clienti_stats,
            eventi=eventi,
            evento_selezionato_id=evento_id,
            giorni=giorni
        )
    finally:
        db.close()


@stats_bp.route("/ingressi")
@require_admin
def admin_ingressi():
    """Statistiche ingressi dettagliate"""
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        giorni = request.args.get("giorni", type=int, default=30)
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        stats = get_ingressi_stats(db, evento_id, giorni)
        
        return render_template(
            "admin/stats_ingressi.html",
            stats=stats,
            eventi=eventi,
            evento_selezionato_id=evento_id,
            giorni=giorni
        )
    finally:
        db.close()


@stats_bp.route("/prenotazioni")
@require_admin
def admin_prenotazioni():
    """Statistiche prenotazioni dettagliate"""
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        stats = get_prenotazioni_stats(db, evento_id)
        
        return render_template(
            "admin/stats_prenotazioni.html",
            stats=stats,
            eventi=eventi,
            evento_selezionato_id=evento_id
        )
    finally:
        db.close()


@stats_bp.route("/consumi")
@require_admin
def admin_consumi():
    """Statistiche consumi dettagliate"""
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        stats = get_consumi_stats(db, evento_id)
        
        return render_template(
            "admin/stats_consumi.html",
            stats=stats,
            eventi=eventi,
            evento_selezionato_id=evento_id
        )
    finally:
        db.close()


@stats_bp.route("/clienti")
@require_admin
def admin_clienti():
    """Statistiche clienti dettagliate"""
    db = SessionLocal()
    try:
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(20).all()
        stats = get_clienti_stats(db)
        
        return render_template(
            "admin/stats_clienti.html",
            stats=stats,
            eventi=eventi
        )
    finally:
        db.close()

