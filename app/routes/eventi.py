# app/routes/eventi.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from werkzeug.utils import secure_filename
from pathlib import Path
import os

from app.database import SessionLocal
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.prenotazioni import Prenotazione
from app.models.consumi import Consumo
from app.models.feedback import Feedback
from app.utils.decorators import require_admin, require_staff
from app.models.template_eventi import TEMPLATE_EVENTI, TemplateEvento

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

eventi_bp = Blueprint("eventi", __name__, url_prefix="/eventi")

CATEGORIES_PUBLIC = ["reggaeton", "techno", "altro"]  # no 'privato' come da tua scelta

# --------------------------
# CLIENTE — LISTA EVENTI PUBBLICI (no login)
# --------------------------
@eventi_bp.route("/", methods=["GET"])
def lista_pubblica():
    db = SessionLocal()
    try:
        q = db.query(Evento).filter(Evento.data_evento >= date.today())

        cat = request.args.get("categoria")
        dal = request.args.get("dal")   # yyyy-mm-dd
        al  = request.args.get("al")    # yyyy-mm-dd

        if cat and cat in CATEGORIES_PUBLIC:
            q = q.filter(Evento.categoria == cat)

        if dal:
            try:
                dal_d = datetime.strptime(dal, "%Y-%m-%d").date()
                q = q.filter(Evento.data_evento >= dal_d)
            except ValueError:
                pass
        if al:
            try:
                al_d = datetime.strptime(al, "%Y-%m-%d").date()
                q = q.filter(Evento.data_evento <= al_d)
            except ValueError:
                pass

        eventi = q.order_by(Evento.data_evento.asc(), Evento.id_evento.asc()).all()
        return render_template("clienti/eventi_list.html",
                               eventi=eventi,
                               CATEGORIES_PUBLIC=CATEGORIES_PUBLIC,
                               filtri={"categoria": cat, "dal": dal, "al": al})
    finally:
        db.close()

# --------------------------
# CLIENTE — DETTAGLIO EVENTO (no capienza per cliente)
# --------------------------
@eventi_bp.route("/<int:evento_id>", methods=["GET"])
def dettaglio_pubblico(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.lista_pubblica"))
        # Non mostriamo capienza residua ai clienti (come concordato)
        return render_template("clienti/evento_detail.html", e=e)
    finally:
        db.close()

# ------------------------------------------------
# STAFF — seleziona evento attivo + dashboard live
# (per ora protetti da require_admin finché non c'è login staff)
# ------------------------------------------------
@eventi_bp.route("/staff/select", methods=["GET", "POST"])
@require_staff
def staff_select_event():
    db = SessionLocal()
    try:
        if request.method == "POST":
            evento_id = request.form.get("evento_id", type=int)
            ev = db.query(Evento).get(evento_id)
            if not ev:
                flash("Evento non valido.", "danger")
            else:
                session["evento_attivo_id"] = evento_id
                flash(f"Evento attivo impostato: {ev.nome_evento}", "success")
                return redirect(url_for("eventi.staff_dashboard"))
        # mostriamo eventi futuri + di oggi
        eventi = db.query(Evento).filter(Evento.data_evento >= date.today()) \
                     .order_by(Evento.data_evento.asc()).all()
        return render_template("staff/evento_select.html", eventi=eventi)
    finally:
        db.close()

@eventi_bp.route("/staff/dashboard", methods=["GET"])
@require_staff
def staff_dashboard():
    evento_id = session.get("evento_attivo_id")
    if not evento_id:
        flash("Seleziona prima un evento attivo.", "warning")
        return redirect(url_for("eventi.staff_select_event"))

    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.staff_select_event"))

        ingressi_tot = db.query(func.count(Ingresso.id_ingresso)) \
                         .filter(Ingresso.evento_id == evento_id).scalar() or 0
        capienza = e.capienza_max or 0
        residua  = max(0, capienza - ingressi_tot)

        # ritmo ultimi 15 minuti
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=15)
        ritmo_15m = db.query(func.count(Ingresso.id_ingresso)) \
                      .filter(and_(Ingresso.evento_id == evento_id,
                                   Ingresso.orario_ingresso >= window_start)) \
                      .scalar() or 0

        return render_template("staff/evento_dashboard.html",
                               e=e,
                               ingressi_tot=ingressi_tot,
                               capienza=capienza,
                               residua=residua,
                               ritmo_15m=ritmo_15m)
    finally:
        db.close()

# --------------------------
# ADMIN — LISTA + CRUD + DUPLICA + CHIUDI + ANALYTICS
# --------------------------
@eventi_bp.route("/admin/menu", methods=["GET"])
@require_admin
def admin_menu():
    """Menu principale per la gestione eventi"""
    db = SessionLocal()
    try:
        from datetime import date
        oggi = date.today()
        
        # Statistiche rapide
        tot_eventi = db.query(func.count(Evento.id_evento)).scalar() or 0
        eventi_attivi = db.query(func.count(Evento.id_evento)).filter(Evento.stato == "attivo").scalar() or 0
        eventi_programmati = db.query(func.count(Evento.id_evento)).filter(Evento.data_evento >= oggi).scalar() or 0
        eventi_passati = db.query(func.count(Evento.id_evento)).filter(Evento.data_evento < oggi).scalar() or 0
        
        # Prossimi 3 eventi
        prossimi_eventi = db.query(Evento).filter(Evento.data_evento >= oggi).order_by(Evento.data_evento.asc()).limit(3).all()
        
        # Ultimi 3 eventi
        ultimi_eventi = db.query(Evento).order_by(Evento.data_evento.desc()).limit(3).all()
        
        return render_template("admin/eventi_menu.html",
                             tot_eventi=tot_eventi,
                             eventi_attivi=eventi_attivi,
                             eventi_programmati=eventi_programmati,
                             eventi_passati=eventi_passati,
                             prossimi_eventi=prossimi_eventi,
                             ultimi_eventi=ultimi_eventi,
                             oggi=oggi)
    finally:
        db.close()

@eventi_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        from datetime import date
        oggi = date.today()
        stato = request.args.get("stato")  # 'attivo'/'chiuso'/None
        periodo = request.args.get("periodo")  # 'programmati'/'passati'/None
        q = db.query(Evento)
        if stato in ("attivo", "chiuso"):
            q = q.filter(Evento.stato == stato)
        if periodo == "programmati":
            q = q.filter(Evento.data_evento >= oggi)
        elif periodo == "passati":
            q = q.filter(Evento.data_evento < oggi)
        eventi = q.order_by(Evento.data_evento.desc()).all()
        
        # Classifica automaticamente gli eventi in base alla data
        eventi_programmati = [e for e in eventi if e.data_evento >= oggi]
        eventi_passati = [e for e in eventi if e.data_evento < oggi]
        
        return render_template("admin/eventi_list.html", 
                             eventi=eventi, 
                             stato=stato, 
                             periodo=periodo,
                             oggi=oggi,
                             eventi_programmati=eventi_programmati,
                             eventi_passati=eventi_passati)
    finally:
        db.close()

@eventi_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        if request.method == "POST":
            cover_filename = None
            if 'cover_image' in request.files:
                file = request.files['cover_image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Genera un nome unico basato su timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    name, ext = os.path.splitext(filename)
                    cover_filename = f"{timestamp}_{name}{ext}"
                    file_path = Path(current_app.config['UPLOAD_FOLDER']) / cover_filename
                    file.save(str(file_path))
            
            e = Evento(
                nome_evento=request.form.get("nome_evento"),
                data_evento=request.form.get("data_evento"),
                tipo_musica=request.form.get("tipo_musica"),
                dj_artista=request.form.get("dj_artista"),
                promozione=request.form.get("promozione"),
                capienza_max=request.form.get("capienza_max", type=int),
                categoria=request.form.get("categoria"),
                stato=request.form.get("stato"),
                cover_url=cover_filename,
                template_id=(
                    int(request.form.get("template_evento").split("-",1)[1])
                    if (request.form.get("template_evento") or '').startswith("db-") else None
                ),
            )
            db.add(e)
            db.commit()
            flash("Evento creato.", "success")
            return redirect(url_for("eventi.admin_evento_detail", evento_id=e.id_evento))
        return render_template("admin/eventi_form.html", e=None, CATEGORIES_PUBLIC=CATEGORIES_PUBLIC, TEMPLATE_EVENTI=TEMPLATE_EVENTI, FORMATS=db.query(TemplateEvento).order_by(TemplateEvento.nome.asc()).all(), template_selezionato=request.args.get("t"))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>", methods=["GET"])
@require_admin
def admin_evento_detail(evento_id):
    db = SessionLocal()
    try:
        from app.models.fedeltà import Fedelta
        from app.models.feedback import Feedback
        from app.models.clienti import Cliente
        from app.models.staff import Staff
        
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))
        
        # Statistiche generali
        tot_prenotazioni = db.query(func.count(Prenotazione.id_prenotazione)).filter(Prenotazione.evento_id == evento_id).scalar() or 0
        tot_ingressi = db.query(func.count(Ingresso.id_ingresso)).filter(Ingresso.evento_id == evento_id).scalar() or 0
        tot_consumi = db.query(func.coalesce(func.sum(Consumo.importo), 0)).filter(Consumo.evento_id == evento_id).scalar() or 0
        tot_consumi = float(tot_consumi) if tot_consumi else 0
        tot_punti_fedelta = db.query(func.sum(Fedelta.punti)).filter(Fedelta.evento_id == evento_id).scalar() or 0
        tot_feedback = db.query(func.count(Feedback.id_feedback)).filter(Feedback.evento_id == evento_id).scalar() or 0
        
        # Liste dettagliate per evento
        prenotazioni_evento = (
            db.query(Prenotazione, Cliente)
              .join(Cliente, Cliente.id_cliente == Prenotazione.cliente_id)
              .filter(Prenotazione.evento_id == evento_id)
              .order_by(Prenotazione.id_prenotazione.desc())
              .all()
        )
        ingressi_evento = (
            db.query(Ingresso, Cliente, Staff)
              .join(Cliente, Cliente.id_cliente == Ingresso.cliente_id)
              .outerjoin(Staff, Staff.id_staff == Ingresso.staff_id)
              .filter(Ingresso.evento_id == evento_id)
              .order_by(Ingresso.orario_ingresso.desc())
              .all()
        )
        consumi_evento = (
            db.query(Consumo, Cliente, Staff)
              .join(Cliente, Cliente.id_cliente == Consumo.cliente_id)
              .outerjoin(Staff, Staff.id_staff == Consumo.staff_id)
              .filter(Consumo.evento_id == evento_id)
              .order_by(Consumo.data_consumo.desc())
              .all()
        )

        feedback_evento = (
            db.query(Feedback, Cliente)
              .join(Cliente, Cliente.id_cliente == Feedback.cliente_id)
              .filter(Feedback.evento_id == evento_id)
              .order_by(Feedback.data_feedback.desc())
              .all()
        )
        
        # Breakdown prenotazioni
        pren_by_tipo = dict(db.query(Prenotazione.tipo, func.count(Prenotazione.id_prenotazione))
                           .filter(Prenotazione.evento_id == evento_id)
                           .group_by(Prenotazione.tipo).all())
        pren_by_stato = dict(db.query(Prenotazione.stato, func.count(Prenotazione.id_prenotazione))
                            .filter(Prenotazione.evento_id == evento_id)
                            .group_by(Prenotazione.stato).all())
        tavolo_persone = db.query(func.coalesce(func.sum(Prenotazione.num_persone), 0)) \
                          .filter(Prenotazione.evento_id == evento_id, Prenotazione.tipo == "tavolo") \
                          .scalar() or 0
        
        # Breakdown ingressi
        ingressi_by_tipo = dict(db.query(Ingresso.tipo_ingresso, func.count(Ingresso.id_ingresso))
                               .filter(Ingresso.evento_id == evento_id)
                               .group_by(Ingresso.tipo_ingresso).all())
        ingressi_by_staff = db.query(Staff.nome, func.count(Ingresso.id_ingresso)) \
                             .join(Ingresso, Ingresso.staff_id == Staff.id_staff) \
                             .filter(Ingresso.evento_id == evento_id) \
                             .group_by(Staff.id_staff, Staff.nome) \
                             .order_by(func.count(Ingresso.id_ingresso).desc()) \
                             .limit(10).all()
        
        # Breakdown consumi
        consumi_by_punto = dict(db.query(Consumo.punto_vendita, func.sum(Consumo.importo))
                               .filter(Consumo.evento_id == evento_id)
                               .group_by(Consumo.punto_vendita).all())
        consumi_by_prodotto = db.query(Consumo.prodotto, func.sum(Consumo.importo), func.count(Consumo.id_consumo)) \
                                .filter(Consumo.evento_id == evento_id) \
                                .group_by(Consumo.prodotto) \
                                .order_by(func.sum(Consumo.importo).desc()) \
                                .limit(10).all()
        clienti_consumi = db.query(func.count(func.distinct(Consumo.cliente_id))) \
                           .filter(Consumo.evento_id == evento_id).scalar() or 0
        scontrino_medio = round(tot_consumi / clienti_consumi, 2) if clienti_consumi else 0
        
        # Top clienti
        top_clienti_consumi = db.query(Cliente, func.sum(Consumo.importo).label("spesa")) \
                                .join(Consumo, Consumo.cliente_id == Cliente.id_cliente) \
                                .filter(Consumo.evento_id == evento_id) \
                                .group_by(Cliente.id_cliente) \
                                .order_by(func.sum(Consumo.importo).desc()) \
                                .limit(10).all()
        
        # Feedback media
        avg_feedback = db.query(
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente)
        ).filter(Feedback.evento_id == evento_id).one()
        
        return render_template("admin/evento_detail.html",
                             evento=e,
                             tot_prenotazioni=tot_prenotazioni,
                             tot_ingressi=tot_ingressi,
                             tot_consumi=tot_consumi,
                             tot_punti_fedelta=tot_punti_fedelta,
                             tot_feedback=tot_feedback,
                             prenotazioni_evento=prenotazioni_evento,
                             ingressi_evento=ingressi_evento,
                             consumi_evento=consumi_evento,
                             feedback_evento=feedback_evento,
                             pren_by_tipo=pren_by_tipo,
                             pren_by_stato=pren_by_stato,
                             tavolo_persone=tavolo_persone,
                             ingressi_by_tipo=ingressi_by_tipo,
                             ingressi_by_staff=ingressi_by_staff,
                             consumi_by_punto=consumi_by_punto,
                             consumi_by_prodotto=consumi_by_prodotto,
                             clienti_consumi=clienti_consumi,
                             scontrino_medio=scontrino_medio,
                             top_clienti_consumi=top_clienti_consumi,
                             avg_musica=round(avg_feedback[0] or 0, 1),
                             avg_ingresso=round(avg_feedback[1] or 0, 1),
                             avg_ambiente=round(avg_feedback[2] or 0, 1),
                             CATEGORIES_PUBLIC=CATEGORIES_PUBLIC)
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))
        if request.method == "POST":
            e.nome_evento = request.form.get("nome_evento")
            e.data_evento = request.form.get("data_evento")
            e.tipo_musica = request.form.get("tipo_musica")
            e.dj_artista = request.form.get("dj_artista")
            e.promozione = request.form.get("promozione")
            e.capienza_max = request.form.get("capienza_max", type=int)
            e.categoria = request.form.get("categoria")
            e.stato = request.form.get("stato")
            
            # Gestione upload immagine
            if 'cover_image' in request.files:
                file = request.files['cover_image']
                if file and file.filename and allowed_file(file.filename):
                    # Elimina vecchia immagine se esiste
                    if e.cover_url:
                        old_path = Path(current_app.config['UPLOAD_FOLDER']) / e.cover_url
                        if old_path.exists():
                            old_path.unlink()
                    
                    # Salva nuova immagine
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    name, ext = os.path.splitext(filename)
                    cover_filename = f"{timestamp}_{name}{ext}"
                    file_path = Path(current_app.config['UPLOAD_FOLDER']) / cover_filename
                    file.save(str(file_path))
                    e.cover_url = cover_filename
                elif request.form.get("remove_cover") == "1":
                    # Rimuovi immagine se richiesto
                    if e.cover_url:
                        old_path = Path(current_app.config['UPLOAD_FOLDER']) / e.cover_url
                        if old_path.exists():
                            old_path.unlink()
                    e.cover_url = None
            
            db.commit()
            flash("Evento aggiornato.", "success")
            return redirect(url_for("eventi.admin_evento_detail", evento_id=evento_id))
        return render_template("admin/eventi_form.html", e=e, CATEGORIES_PUBLIC=CATEGORIES_PUBLIC)
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/delete", methods=["POST"])
@require_admin
def admin_delete(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
        else:
            # Elimina immagine se esiste
            if e.cover_url:
                img_path = Path(current_app.config['UPLOAD_FOLDER']) / e.cover_url
                if img_path.exists():
                    img_path.unlink()
            db.delete(e)
            db.commit()
            flash("Evento eliminato.", "warning")
        return redirect(url_for("eventi.admin_list"))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/duplicate", methods=["POST"])
@require_admin
def admin_duplicate(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))
        new_date = request.form.get("data_evento") or e.data_evento
        dup = Evento(
            nome_evento=f"{e.nome_evento} (copy)",
            data_evento=new_date,
            tipo_musica=e.tipo_musica,
            dj_artista=e.dj_artista,
            promozione=e.promozione,
            capienza_max=e.capienza_max,
            categoria=e.categoria if e.categoria in CATEGORIES_PUBLIC else "altro",
            stato="attivo",
            cover_url=None  # Non copiare l'immagine nella duplicazione
        )
        db.add(dup)
        db.commit()
        flash("Evento duplicato.", "success")
        return redirect(url_for("eventi.admin_evento_detail", evento_id=dup.id_evento))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/close", methods=["POST"])
@require_admin
def admin_close(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
        else:
            e.stato = "chiuso"
            db.commit()
            flash("Evento chiuso.", "success")
        return redirect(url_for("eventi.admin_evento_detail", evento_id=evento_id))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/analytics", methods=["GET"])
@require_admin
def admin_analytics(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))

        ingressi_tot = (db.query(func.count(Ingresso.id_ingresso))
                          .filter(Ingresso.evento_id == evento_id)
                          .scalar()) or 0

        pren_by_tipo_items = (db.query(Prenotazione.tipo,
                                       func.count(Prenotazione.id_prenotazione))
                              .filter(Prenotazione.evento_id == evento_id)
                                .group_by(Prenotazione.tipo)
                                .all())
        pren_by_tipo = {tipo or "non_specificato": count for tipo, count in pren_by_tipo_items}

        consumi_sum = (db.query(func.coalesce(func.sum(Consumo.importo), 0))
                         .filter(Consumo.evento_id == evento_id)
                         .scalar()) or 0

        ingressi_per_evento_rows = (
            db.query(
                Evento.nome_evento,
                Evento.categoria,
                func.count(Ingresso.id_ingresso).label("tot_ingressi")
            )
            .outerjoin(Ingresso, Ingresso.evento_id == Evento.id_evento)
            .group_by(Evento.id_evento, Evento.nome_evento, Evento.categoria)
            .order_by(func.count(Ingresso.id_ingresso).desc())
            .limit(20)
            .all()
        )

        ingressi_per_evento_items = []
        ingressi_categories = set()
        for row in ingressi_per_evento_rows:
            categoria = row.categoria or "non specificato"
            ingressi_categories.add(categoria)
            ingressi_per_evento_items.append({
                "label": row.nome_evento,
                "count": int(row.tot_ingressi or 0),
                "categoria": categoria,
            })

        ingressi_per_evento = {
            "items": ingressi_per_evento_items,
            "categories": sorted(ingressi_categories),
        }

        feedback_media_row = (db.query(
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente),
            func.count(Feedback.id_feedback)
        )
            .filter(Feedback.evento_id == evento_id)
            .one())

        feedback_media = None
        if feedback_media_row and feedback_media_row[3]:
            valori_feedback = [
                float(feedback_media_row[0] or 0),
                float(feedback_media_row[1] or 0),
                float(feedback_media_row[2] or 0),
            ]
            feedback_media = {
                "labels": ["Musica", "Ingresso", "Ambiente"],
                "values": valori_feedback,
                "samples": int(feedback_media_row[3]),
                "average": (sum(valori_feedback) / len(valori_feedback)) if valori_feedback else 0.0,
            }

        slot_expr = func.date_format(Ingresso.orario_ingresso, "%Y-%m-%d %H:00")
        ingressi_temporali_rows = (
            db.query(
                slot_expr.label("slot"),
                func.count(Ingresso.id_ingresso).label("tot_slot")
            )
            .filter(Ingresso.evento_id == evento_id)
            .group_by(slot_expr)
            .order_by(slot_expr)
            .all()
        )

        ingressi_temporali_points = []
        for row in ingressi_temporali_rows:
            slot_str = row.slot
            ingressi_temporali_points.append({
                "slot": slot_str,
                "value": int(row.tot_slot or 0),
            })

        ingressi_temporali = {
            "points": ingressi_temporali_points,
        }

        prodotti_top_rows = (
            db.query(
                Consumo.prodotto,
                func.count(Consumo.id_consumo).label("quantita"),
                func.coalesce(func.sum(Consumo.importo), 0).label("ricavi")
            )
            .filter(Consumo.evento_id == evento_id)
            .group_by(Consumo.prodotto)
            .order_by(func.count(Consumo.id_consumo).desc())
            .limit(10)
            .all()
        )

        prodotti_top_items = []
        for row in prodotti_top_rows:
            prodotti_top_items.append({
                "label": row.prodotto,
                "count": int(row.quantita or 0),
                "revenue": float(row.ricavi or 0),
            })

        prodotti_top = {
            "items": prodotti_top_items,
        }

        prenotazioni_chart = {
            "items": [
                {
                    "label": label,
                    "value": int(value or 0),
                }
                for label, value in pren_by_tipo.items()
            ] or [{"label": "Nessuna", "value": 0}],
        }

        return render_template(
            "admin/analytics/evento_dashboard.html",
                               e=e,
                               ingressi_tot=ingressi_tot,
                               pren_by_tipo=pren_by_tipo,
            consumi_sum=float(consumi_sum),
            ingressi_per_evento=ingressi_per_evento,
            feedback_media=feedback_media,
            ingressi_temporali=ingressi_temporali,
            prodotti_top=prodotti_top,
            prenotazioni_chart=prenotazioni_chart,
        )
    finally:
        db.close()