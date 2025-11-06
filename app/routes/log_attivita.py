# app/routes/log_attivita.py
from flask import Blueprint, render_template, request
from sqlalchemy import and_
from app.database import SessionLocal
from app.utils.decorators import require_admin
from app.models.log_attivita import LogAttivita
from app.models.staff import Staff

log_bp = Blueprint("log", __name__, url_prefix="/admin/logs")

# Utility importabile per registrare log ovunque
def log_action(db, *, tabella: str, record_id: int, staff_id: int | None, azione: str):
    entry = LogAttivita(tabella=tabella, record_id=record_id, staff_id=staff_id, azione=azione)
    db.add(entry)
    # commit delegato al chiamante per transazioni atomiche

@log_bp.route("/")
@require_admin
def list():
    db = SessionLocal()
    try:
        tabella = request.args.get("tabella")
        staff_id = request.args.get("staff_id", type=int)
        azione = request.args.get("azione")
        dal = request.args.get("dal")
        al = request.args.get("al")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        q = db.query(LogAttivita, Staff).outerjoin(Staff, LogAttivita.staff_id == Staff.id_staff)
        if tabella:
            q = q.filter(LogAttivita.tabella == tabella)
        if staff_id:
            q = q.filter(LogAttivita.staff_id == staff_id)
        if azione:
            q = q.filter(LogAttivita.azione == azione)
        if dal:
            q = q.filter(LogAttivita.timestamp >= dal)
        if al:
            q = q.filter(LogAttivita.timestamp <= al)

        total = q.count()
        rows = (
            q.order_by(LogAttivita.timestamp.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        staffs = db.query(Staff).order_by(Staff.nome.asc()).all()

        return render_template(
            "admin/log_list.html",
            rows=rows,
            total=total,
            page=page,
            per_page=per_page,
            staffs=staffs,
            filtro_tabella=tabella,
            filtro_staff_id=staff_id,
            filtro_azione=azione,
            filtro_dal=dal,
            filtro_al=al,
        )
    finally:
        db.close()

