# app/routes/eventi.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import shutil

from app.database import SessionLocal
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.prenotazioni import Prenotazione
from app.models.consumi import Consumo
from app.models.feedback import Feedback
from app.utils.decorators import require_admin, require_staff
from app.models.template_eventi import TEMPLATE_EVENTI, TemplateEvento
from app.utils.events import get_evento_operativo, set_evento_operativo_id
from app.routes.log_attivita import log_action
from app.routes.fedelta import award_on_no_show

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

eventi_bp = Blueprint("eventi", __name__, url_prefix="/eventi")

CATEGORIES_PUBLIC = ["reggaeton", "techno", "altro"]  # categorie pubbliche esposte a UI


# Helper: usa direttamente get_evento_operativo dal modulo events

# --------------------------
# CLIENTE — LISTA EVENTI PUBBLICI (no login)
# --------------------------
@eventi_bp.route("/", methods=["GET"])
def lista_pubblica():
    from app.utils.workflow import get_workflow_state, evento_stato_badge
    db = SessionLocal()
    try:
        cat = request.args.get("categoria")
        dal = request.args.get("dal")   # yyyy-mm-dd
        al  = request.args.get("al")    # yyyy-mm-dd
        # Costruisce filtro base da riusare
        def apply_common_filters(query):
            if cat and cat in CATEGORIES_PUBLIC:
                query = query.filter(Evento.categoria == cat)
            if dal:
                try:
                    dal_d = datetime.strptime(dal, "%Y-%m-%d").date()
                    query = query.filter(Evento.data_evento >= dal_d)
                except ValueError:
                    pass
            if al:
                try:
                    al_d = datetime.strptime(al, "%Y-%m-%d").date()
                    query = query.filter(Evento.data_evento <= al_d)
                except ValueError:
                    pass
            return query

        oggi = date.today()
        # Prossimi eventi (oggi e futuri)
        q_next = apply_common_filters(
            db.query(Evento)
              .filter(Evento.data_evento >= oggi)
        )
        eventi_prossimi = q_next.order_by(Evento.data_evento.asc(), Evento.id_evento.asc()).all()

        # Eventi passati (ultimi 10, più "grigi" a UI)
        show_all = request.args.get("show_all")
        show_all_past = (show_all == "past")

        q_past = apply_common_filters(db.query(Evento).filter(Evento.data_evento < oggi))
        q_past = q_past.order_by(Evento.data_evento.desc(), Evento.id_evento.desc())
        if not show_all_past:
            q_past = q_past.limit(20)
        eventi_passati = q_past.all()

        # Stato prenotazioni e workflow per cliente loggato
        prenotati_ids = set()
        workflow_map = {}  # { evento_id: workflow_state }
        cid = session.get("cliente_id")
        if cid and eventi_prossimi:
            prenotati_ids = {
                pid for (pid,) in db.query(Prenotazione.evento_id)
                .filter(
                    Prenotazione.cliente_id == cid,
                    Prenotazione.evento_id.in_([e.id_evento for e in eventi_prossimi]),
                    Prenotazione.stato.in_(("attiva", "usata"))
                )
                .all()
            }
            # Crea workflow state per ogni evento
            for ev in eventi_prossimi:
                workflow_map[ev.id_evento] = get_workflow_state(db, cid, ev.id_evento)

        # Badge per stato evento
        evento_badge_map = {}
        for ev in eventi_prossimi + eventi_passati:
            evento_badge_map[ev.id_evento] = evento_stato_badge(ev)

        return render_template("clienti/eventi_list.html",
                               eventi_prossimi=eventi_prossimi,
                               eventi_passati=eventi_passati,
                               eventi_prenotati=prenotati_ids,
                               workflow_map=workflow_map,
                               evento_badge_map=evento_badge_map,
                               CATEGORIES_PUBLIC=CATEGORIES_PUBLIC,
                               filtri={"categoria": cat, "dal": dal, "al": al},
                               show_all_past=show_all_past)
    finally:
        db.close()

# --------------------------
# CLIENTE — DETTAGLIO EVENTO (no capienza per cliente)
# --------------------------
@eventi_bp.route("/<int:evento_id>", methods=["GET"])
def dettaglio_pubblico(evento_id):
    from app.utils.workflow import get_workflow_state, evento_stato_badge
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.lista_pubblica"))
        
        # Mostra eventuali acquisti dell'utente loggato durante la serata
        consumi_miei = []
        workflow_state = None
        cid = session.get("cliente_id")
        if cid:
            consumi_miei = (db.query(Consumo)
                              .filter(Consumo.evento_id == evento_id, Consumo.cliente_id == cid)
                              .order_by(Consumo.data_consumo.desc())
                              .all())
            # Workflow state per il cliente
            workflow_state = get_workflow_state(db, cid, evento_id)
        
        is_future = e.data_evento >= date.today()
        evento_badge = evento_stato_badge(e)
        
        return render_template("clienti/evento_detail.html",
                             e=e,
                             consumi_miei=consumi_miei,
                             workflow_state=workflow_state,
                             evento_badge=evento_badge,
                             is_future=is_future)
    finally:
        db.close()

# ------------------------------------------------
# STAFF — seleziona evento attivo + dashboard live
# (per ora protetti da require_admin finché non c'è login staff)
# ------------------------------------------------
@eventi_bp.route("/staff/select", methods=["GET"])
@require_staff
def staff_select_event():
    db = SessionLocal()
    try:
        evento_attivo = get_evento_operativo(db)
        # Includiamo anche gli eventi di "ieri" per coprire serate a cavallo della mezzanotte
        window_start = date.today() - timedelta(days=1)
        eventi = (db.query(Evento)
                    .filter(Evento.data_evento >= window_start)
                    .order_by(Evento.data_evento.asc())
                    .all())
        return render_template("staff/evento_select.html", evento_attivo=evento_attivo, eventi=eventi)
    finally:
        db.close()

@eventi_bp.route("/staff/dashboard", methods=["GET"])
@require_staff
def staff_dashboard():
    db = SessionLocal()
    try:
        e = get_evento_operativo(db)
        if not e:
            flash("Nessun evento attivo impostato dagli amministratori.", "warning")
            return redirect(url_for("eventi.staff_select_event"))

        evento_id = e.id_evento
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


@eventi_bp.route("/admin/evento-attivo", methods=["GET", "POST"])
@require_admin
def admin_evento_attivo():
    db = SessionLocal()
    try:
        # includi anche ieri (overnight)
        window_start = date.today() - timedelta(days=1)
        eventi = (db.query(Evento)
                    .filter(Evento.data_evento >= window_start)
                    .order_by(Evento.data_evento.asc())
                    .all())
        ingressi_map = {}
        if eventi:
            ids = [ev.id_evento for ev in eventi]
            counts = (db.query(Ingresso.evento_id, func.count(Ingresso.id_ingresso))
                        .filter(Ingresso.evento_id.in_(ids))
                        .group_by(Ingresso.evento_id)
                        .all())
            ingressi_map = {eid: tot for eid, tot in counts}
        evento_attivo = get_evento_operativo(db)

        if request.method == "POST":
            action = request.form.get("action")
            if action == "clear":
                # Disattiva operatività per tutti e azzera config
                for ev in db.query(Evento).filter(Evento.is_staff_operativo == True).all():
                    ev.is_staff_operativo = False
                db.commit()
                set_evento_operativo_id(db, None)
                log_action(
                    db,
                    tabella="eventi",
                    record_id=0,
                    staff_id=session.get("staff_id"),
                    azione="unset_operativo",
                    note="evento_id=None"
                )
                flash("Evento operativo staff azzerato.", "info")
            else:
                scelta = request.form.get("evento_id")
                if not scelta:
                    flash("Seleziona un evento o azzera l'evento attivo.", "warning")
                    return redirect(url_for("eventi.admin_evento_attivo"))
                try:
                    evento_id = int(scelta)
                except (TypeError, ValueError):
                    flash("Selezione non valida.", "danger")
                    return redirect(url_for("eventi.admin_evento_attivo"))

                ev = db.query(Evento).get(evento_id)
                if not ev:
                    flash("Evento non valido.", "danger")
                else:
                    # Assicura unicità: spegni gli altri e abilita questo
                    for other in db.query(Evento).filter(Evento.is_staff_operativo == True).all():
                        other.is_staff_operativo = False
                    ev.is_staff_operativo = True
                    db.commit()
                    set_evento_operativo_id(db, ev.id_evento)
                    log_action(
                        db,
                        tabella="eventi",
                        record_id=ev.id_evento,
                        staff_id=session.get("staff_id"),
                        azione="set_operativo",
                        note=f"evento_id={ev.id_evento}"
                    )
                    flash(f"Evento operativo staff impostato su {ev.nome_evento}.", "success")
            return redirect(url_for("eventi.admin_evento_attivo"))

        return render_template("admin/evento_attivo.html",
                               eventi=eventi,
                               evento_attivo=evento_attivo,
                               ingressi_map=ingressi_map)
    finally:
        db.close()

# --------------------------
# ADMIN — LISTA + CRUD + DUPLICA + CHIUDI + ANALYTICS
# --------------------------
@eventi_bp.route("/admin/menu", methods=["GET"])
@require_admin
def admin_menu():
    """Route deprecata: reindirizza alla lista eventi"""
    flash("La pagina menu eventi è stata rimossa. Usa la lista eventi per gestire gli eventi.", "info")
    return redirect(url_for("eventi.admin_list"))

@eventi_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        from datetime import date
        oggi = date.today()
        stato = request.args.get("stato")  # 'programmato'/'attivo'/'chiuso'/None
        periodo = request.args.get("periodo")  # 'programmati'/'passati'/None
        q = db.query(Evento)
        if stato in ("programmato", "attivo", "chiuso"):
            q = q.filter(Evento.stato_pubblico == stato)
        if periodo == "programmati":
            q = q.filter(Evento.data_evento >= oggi)
        elif periodo == "passati":
            q = q.filter(Evento.data_evento < oggi)
        eventi = q.order_by(Evento.data_evento.asc()).all()
        evento_ids = [ev.id_evento for ev in eventi]

        ingressi_map = {}
        if evento_ids:
            counts = (db.query(Ingresso.evento_id, func.count(Ingresso.id_ingresso))
                        .filter(Ingresso.evento_id.in_(evento_ids))
                        .group_by(Ingresso.evento_id)
                        .all())
            ingressi_map = {eid: count for eid, count in counts}
        
        # Classifica automaticamente gli eventi in base alla data
        # Eventi programmati: ordine crescente (prossimo in alto)
        eventi_programmati = sorted([e for e in eventi if e.data_evento >= oggi], 
                                   key=lambda e: e.data_evento)
        # Eventi passati: ordine decrescente (più recente in alto)
        eventi_passati = sorted([e for e in eventi if e.data_evento < oggi], 
                               key=lambda e: e.data_evento, reverse=True)
        
        return render_template("admin/eventi_list.html", 
                             eventi=eventi, 
                             stato=stato, 
                             periodo=periodo,
                             oggi=oggi,
                             eventi_programmati=eventi_programmati,
                             eventi_passati=eventi_passati,
                             ingressi_map=ingressi_map)
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
                stato_pubblico=(request.form.get("stato_pubblico") or "programmato"),
                is_staff_operativo=False,
                cover_url=cover_filename,
                template_id=(
                    int(request.form.get("template_evento").split("-",1)[1])
                    if (request.form.get("template_evento") or '').startswith("db-") else None
                ),
            )
            db.add(e)
            db.flush()
            log_action(
                db,
                tabella="eventi",
                record_id=e.id_evento,
                staff_id=session.get("staff_id"),
                azione="evento_create",
                note=f"evento_id={e.id_evento}"
            )
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
            func.avg(Feedback.voto_ambiente),
            func.avg(Feedback.voto_servizio)
        ).filter(Feedback.evento_id == evento_id).one()
        
        # Dati per grafici analytics
        # Ingressi per ora
        ingressi_ora = db.query(
            func.hour(Ingresso.orario_ingresso).label('ora'),
            func.count(Ingresso.id_ingresso).label('count')
        ).filter(Ingresso.evento_id == evento_id).group_by(func.hour(Ingresso.orario_ingresso)).order_by(func.hour(Ingresso.orario_ingresso)).all()
        
        ingressi_temporali_data = []
        for ora, count in ingressi_ora:
            ingressi_temporali_data.append({'slot': f"{ora:02d}:00", 'value': count})
        
        # Prenotazioni per tipo (per grafico)
        prenotazioni_chart_data = [{'label': tipo.capitalize(), 'value': count} for tipo, count in pren_by_tipo.items()]
        
        # Prodotti top (per grafico)
        prodotti_chart_data = [{'label': prodotto, 'count': count, 'revenue': float(importo)} for prodotto, importo, count in consumi_by_prodotto]
        
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
                             avg_servizio=round(avg_feedback[3] or 0, 1),
                             ingressi_temporali_data=ingressi_temporali_data,
                             prenotazioni_chart_data=prenotazioni_chart_data,
                             prodotti_chart_data=prodotti_chart_data,
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
            e.stato_pubblico = request.form.get("stato_pubblico") or e.stato_pubblico
            
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

@eventi_bp.route("/admin/<int:evento_id>/attiva-pubblico", methods=["POST"])
@require_admin
def admin_attiva_pubblico(evento_id):
    """Attiva l'evento al pubblico (stato_pubblico = 'attivo')"""
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))
        e.stato_pubblico = "attivo"
        db.commit()
        log_action(db, tabella="eventi", record_id=evento_id, staff_id=session.get("staff_id"), azione="update", note="stato_pubblico=attivo")
        flash(f"Evento '{e.nome_evento}' attivato al pubblico.", "success")
        return redirect(url_for("eventi.admin_list"))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/chiudi-pubblico", methods=["POST"])
@require_admin
def admin_chiudi_pubblico(evento_id):
    """Chiude l'evento al pubblico (stato_pubblico = 'chiuso')"""
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("eventi.admin_list"))
        e.stato_pubblico = "chiuso"
        db.commit()
        log_action(db, tabella="eventi", record_id=evento_id, staff_id=session.get("staff_id"), azione="update", note="stato_pubblico=chiuso")
        flash(f"Evento '{e.nome_evento}' chiuso al pubblico.", "info")
        return redirect(url_for("eventi.admin_list"))
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
        new_date = request.form.get("data_evento")
        if not new_date:
            # default a oggi + 7 giorni
            new_date = (date.today() + timedelta(days=7)).isoformat()
        # warning se esiste già evento con stessa data
        exists_same_date = db.query(Evento.id_evento).filter(Evento.data_evento == new_date).first()
        if exists_same_date:
            flash("Attenzione: esiste già un evento con la stessa data.", "warning")
        dup = Evento(
            nome_evento=f"{e.nome_evento} • {new_date}",
            data_evento=new_date,
            tipo_musica=e.tipo_musica,
            dj_artista=e.dj_artista,
            promozione=e.promozione,
            capienza_max=e.capienza_max,
            categoria=e.categoria if e.categoria in CATEGORIES_PUBLIC else "altro",
            stato_pubblico="programmato",
            is_staff_operativo=False,
            cover_url=None
        )
        db.add(dup)
        db.flush()
        # Duplica cover se richiesto e presente
        if request.form.get("duplica_cover") == "1" and e.cover_url:
            src = Path(current_app.config['UPLOAD_FOLDER']) / e.cover_url
            if src.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(e.cover_url)
                new_cover = f"{timestamp}_{name}{ext}"
                dst = Path(current_app.config['UPLOAD_FOLDER']) / new_cover
                try:
                    shutil.copyfile(str(src), str(dst))
                    dup.cover_url = new_cover
                except Exception:
                    pass
        log_action(
            db,
            tabella="eventi",
            record_id=dup.id_evento,
            staff_id=session.get("staff_id"),
            azione="evento_duplicate",
            note=f"evento_id={dup.id_evento}"
        )
        db.commit()
        flash("Evento duplicato.", "success")
        return redirect(url_for("eventi.admin_evento_detail", evento_id=dup.id_evento))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/close", methods=["POST"])
@require_admin
def admin_close(evento_id):
    from app.utils.workflow import processa_no_show_automatico
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
        else:
            # Chiusura atomica: stato finale + cleanup operatività + prenotazioni residue a no-show
            e.stato_pubblico = "chiuso"
            e.is_staff_operativo = False
            # reset fonte unica evento operativo
            set_evento_operativo_id(db, None)
            
            # ⚡ Usa funzione centralizzata per processare no-show
            count_marcate, count_già, count_con_ingresso = processa_no_show_automatico(db, evento_id=evento_id)
            
            log_action(
                db,
                tabella="eventi",
                record_id=evento_id,
                staff_id=session.get("staff_id"),
                azione="event_close",
                note=f"evento_id={evento_id}, no_show_processati={count_marcate}"
            )
            db.commit()
            
            if count_marcate > 0:
                flash(f"Evento chiuso. {count_marcate} prenotazione/i marcate come no-show.", "success")
            else:
                flash("Evento chiuso. Nessuna prenotazione da processare.", "success")
        return redirect(url_for("eventi.admin_evento_detail", evento_id=evento_id))
    finally:
        db.close()

@eventi_bp.route("/admin/<int:evento_id>/analytics", methods=["GET"])
@require_admin
def admin_analytics(evento_id):
    """Vista legacy: reindirizza alla nuova pagina unificata di dettaglio evento."""
    return redirect(url_for("eventi.admin_evento_detail", evento_id=evento_id))