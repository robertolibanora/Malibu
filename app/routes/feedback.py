# app/routes/feedback.py
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import and_, func
from app.database import SessionLocal
from app.utils.decorators import require_cliente, require_admin
from app.models.feedback import Feedback
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.clienti import Cliente

feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")

# -----------------------
# CLIENTE
# -----------------------
@feedback_bp.route("/miei")
@require_cliente
def miei():
    db = SessionLocal()
    try:
        cliente_id = session.get("cliente_id")
        fb = (
            db.query(Feedback, Evento)
            .join(Evento, Evento.id_evento == Feedback.evento_id)
            .filter(Feedback.cliente_id == cliente_id)
            .order_by(Feedback.data_feedback.desc())
            .all()
        )
        return render_template("clienti/feedback_miei.html", feedbacks=fb)
    finally:
        db.close()

@feedback_bp.route("/nuovo", methods=["GET", "POST"])
@require_cliente
def nuovo():
    db = SessionLocal()
    try:
        cliente_id = session.get("cliente_id")
        evento_id = request.args.get("evento_id") or request.form.get("evento_id")

        # lista eventi passati a cui il cliente è entrato (per tendina)
        eventi_ok = (
            db.query(Evento)
            .join(Ingresso, Ingresso.evento_id == Evento.id_evento)
            .filter(Ingresso.cliente_id == cliente_id)
            .order_by(Evento.data_evento.desc())
            .all()
        )

        if request.method == "POST":
            if not evento_id:
                flash("Seleziona un evento.", "error")
                return redirect(url_for("feedback.nuovo"))

            # verifica che il cliente abbia ingresso registrato su quell'evento
            check_ing = (
                db.query(Ingresso)
                .filter(and_(Ingresso.cliente_id == cliente_id, Ingresso.evento_id == int(evento_id)))
                .first()
            )
            if not check_ing:
                flash("Puoi lasciare feedback solo per eventi a cui sei entrato.", "error")
                return redirect(url_for("feedback.nuovo"))

            # evita duplicati cliente+evento (uno per evento)
            dup = (
                db.query(Feedback)
                .filter(and_(Feedback.cliente_id == cliente_id, Feedback.evento_id == int(evento_id)))
                .first()
            )
            if dup:
                flash("Hai già lasciato un feedback per questo evento.", "warning")
                return redirect(url_for("feedback.miei"))

            voto_musica = int(request.form.get("voto_musica", 0))
            voto_ingresso = int(request.form.get("voto_ingresso", 0))
            voto_ambiente = int(request.form.get("voto_ambiente", 0))
            note = request.form.get("note") or None

            fb = Feedback(
                cliente_id=cliente_id,
                evento_id=int(evento_id),
                voto_musica=voto_musica,
                voto_ingresso=voto_ingresso,
                voto_ambiente=voto_ambiente,
                note=note,
            )
            db.add(fb)
            db.commit()
            flash("Feedback inviato, grazie!", "success")
            return redirect(url_for("feedback.miei"))

        return render_template("shared/feedback_form.html", eventi=eventi_ok, evento_id=evento_id)
    finally:
        db.close()

# -----------------------
# ADMIN
# -----------------------
@feedback_bp.route("/admin")
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        cliente_id = request.args.get("cliente_id", type=int)
        dal = request.args.get("dal")
        al = request.args.get("al")

        q = (
            db.query(Feedback, Cliente, Evento)
            .join(Cliente, Cliente.id_cliente == Feedback.cliente_id)
            .join(Evento, Evento.id_evento == Feedback.evento_id)
        )
        if evento_id:
            q = q.filter(Feedback.evento_id == evento_id)
        if cliente_id:
            q = q.filter(Feedback.cliente_id == cliente_id)
        if dal:
            q = q.filter(Feedback.data_feedback >= dal)
        if al:
            q = q.filter(Feedback.data_feedback <= al)

        # Parametri paginazione
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 10), 200)
        
        # Conta totale
        total = q.count()
        
        # Applica paginazione
        rows = q.order_by(Feedback.data_feedback.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()

        # analytics rapidi
        agg = (
            db.query(
                func.count(Feedback.id_feedback),
                func.avg(Feedback.voto_musica),
                func.avg(Feedback.voto_ingresso),
                func.avg(Feedback.voto_ambiente),
            )
        )
        if evento_id:
            agg = agg.filter(Feedback.evento_id == evento_id)
        count, avg_musica, avg_ingresso, avg_ambiente = agg.one()

        # Calcola pagine
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))

        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()

        return render_template(
            "admin/feedback_list.html",
            rows=rows,
            eventi=eventi,
            filtro_evento_id=evento_id,
            count=count or 0,
            avg_musica=round(avg_musica or 0, 2),
            avg_ingresso=round(avg_ingresso or 0, 2),
            avg_ambiente=round(avg_ambiente or 0, 2),
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            pages_list=pages_list,
        )
    finally:
        db.close()

@feedback_bp.route("/admin/<int:id_feedback>/delete", methods=["POST"])
@require_admin
def admin_delete(id_feedback):
    db = SessionLocal()
    try:
        fb = db.query(Feedback).get(id_feedback)
        if not fb:
            flash("Feedback non trovato.", "error")
            return redirect(url_for("feedback.admin_list"))
        db.delete(fb)
        db.commit()
        flash("Feedback eliminato.", "success")
        next_url = request.form.get("next")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("feedback.admin_list"))
    finally:
        db.close()

