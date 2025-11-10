# app/routes/log_attivita.py
from flask import Blueprint, render_template, request
from sqlalchemy import and_
from app.database import SessionLocal
from app.utils.decorators import require_admin
from app.models.log_attivita import LogAttivita
from app.models.staff import Staff
from app.models.consumi import Consumo
from app.models.ingressi import Ingresso
from app.models.clienti import Cliente

log_bp = Blueprint("log", __name__, url_prefix="/admin/logs")

# Utility importabile per registrare log ovunque
def log_action(db, *, tabella: str, record_id: int, staff_id: int | None, azione: str, note: str | None = None):
    entry = LogAttivita(tabella=tabella, record_id=record_id, staff_id=staff_id, azione=azione, note=note)
    db.add(entry)
    # commit delegato al chiamante per transazioni atomiche

@log_bp.route("/")
@require_admin
def list():
    db = SessionLocal()
    try:
        tabella = request.args.get("tabella")
        staff_id = request.args.get("staff_id", type=int)
        tipo = request.args.get("tipo")  # "ingressi" | "vendite"
        dal = request.args.get("dal")
        al = request.args.get("al")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        q = db.query(LogAttivita, Staff).outerjoin(Staff, LogAttivita.staff_id == Staff.id_staff)
        # Filtro per tipo alto livello
        if tipo == "ingressi":
            q = q.filter(LogAttivita.tabella == "ingressi")
        elif tipo == "vendite":
            q = q.filter(LogAttivita.tabella == "consumi")
        # Filtro diretto per tabella (opzionale, più tecnico)
        if tabella:
            q = q.filter(LogAttivita.tabella == tabella)
        if staff_id:
            q = q.filter(LogAttivita.staff_id == staff_id)
        if dal:
            q = q.filter(LogAttivita.timestamp >= dal)
        if al:
            q = q.filter(LogAttivita.timestamp <= al)

        total = q.count()
        base_rows = (
            q.order_by(LogAttivita.timestamp.desc())
             .offset((page - 1) * per_page)
             .limit(per_page)
             .all()
        )
        staffs = db.query(Staff).order_by(Staff.nome.asc()).all()

        # Enrich: dettaglio umano leggibile
        enriched_rows = []
        for log, staff in base_rows:
            detail = None
            if log.tabella == "consumi":
                c = db.query(Consumo).get(log.record_id)
                if c:
                    cli = db.query(Cliente).get(c.cliente_id)
                    cliente_nome = f"{cli.nome} {cli.cognome}" if cli else "cliente sconosciuto"
                    detail = f"Vendita: {c.prodotto} a {cliente_nome} (€{float(c.importo):.2f})"
            elif log.tabella == "ingressi":
                ing = db.query(Ingresso).get(log.record_id)
                if ing:
                    cli = db.query(Cliente).get(ing.cliente_id)
                    cliente_nome = f"{cli.nome} {cli.cognome}" if cli else "cliente sconosciuto"
                    detail = f"Ingresso registrato: {ing.tipo_ingresso} per {cliente_nome}"
            enriched_rows.append((log, staff, detail))

        return render_template(
            "admin/log_list.html",
            rows=enriched_rows,
            total=total,
            page=page,
            per_page=per_page,
            staffs=staffs,
            filtro_tabella=tabella,
            filtro_staff_id=staff_id,
            filtro_tipo=tipo,
            filtro_dal=dal,
            filtro_al=al,
        )
    finally:
        db.close()

