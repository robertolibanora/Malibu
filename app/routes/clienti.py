from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.clienti import Cliente
from app.models.prenotazioni import Prenotazione
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.consumi import Consumo
from app.utils.qr import qr_data_url
from app.utils.auth import hash_password
from app.routes.fedelta import get_thresholds, compute_level, next_threshold_info
from app.utils.decorators import require_cliente, require_admin
from app.utils.events import get_evento_operativo
from app.utils.helpers import get_current_cliente as current_cliente
from datetime import datetime, date, timedelta

clienti_bp = Blueprint("clienti", __name__, url_prefix="/clienti")
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


# -----------------------
# AREA PERSONALE CLIENTE
# -----------------------
@clienti_bp.route("/me", methods=["GET"])
@require_cliente
def area_personale():
    db = SessionLocal()
    try:
        cli = current_cliente(db)
        if not cli:
            session.pop("cliente_id", None)
            flash("La tua sessione non è più valida. Effettua di nuovo l'accesso.", "warning")
            return redirect(url_for("auth.auth_login_cliente_form"))
        # Prepara QR in data URL per embed
        qr_url = qr_data_url(cli.qr_code) if cli and cli.qr_code else None

        prenotazioni_future = (
            db.query(Prenotazione)
            .join(Prenotazione.evento)
            .options(joinedload(Prenotazione.evento))
            .filter(
                Prenotazione.cliente_id == cli.id_cliente,
                Evento.data_evento >= date.today(),
                Prenotazione.stato.in_(["attiva"]),
            )
            .order_by(Evento.data_evento.asc())
            .limit(3)
            .all()
        )

        prenotazioni_passate = (
            db.query(Prenotazione)
            .join(Prenotazione.evento)
            .options(joinedload(Prenotazione.evento))
            .filter(
                Prenotazione.cliente_id == cli.id_cliente,
                Evento.data_evento < date.today(),
                Prenotazione.stato.in_(["usata", "no-show", "cancellata"]),
            )
            .order_by(Evento.data_evento.desc())
            .limit(3)
            .all()
        )

        ultimo_ingresso = (
            db.query(Ingresso)
            .join(Ingresso.evento)
            .options(joinedload(Ingresso.evento))
            .filter(Ingresso.cliente_id == cli.id_cliente)
            .order_by(Ingresso.orario_ingresso.desc())
            .first()
        )

        consumi_recenti = (
            db.query(Consumo)
            .join(Consumo.evento)
            .options(joinedload(Consumo.evento))
            .filter(Consumo.cliente_id == cli.id_cliente)
            .order_by(Consumo.data_consumo.desc())
            .limit(3)
            .all()
        )

        # Fedeltà: calcolo progress bar e info livello
        thr = get_thresholds(db)
        points = int(cli.punti_fedelta or 0)
        current_level = compute_level(points, thr)
        nxt, to_go = next_threshold_info(points, thr)
        next_points = thr.get(nxt) if nxt else None
        if nxt:
            prev_min = max([v for k, v in thr.items() if v <= points])
            denom = max(1, (next_points - prev_min))
            progress = int(100 * (points - prev_min) / denom)
        else:
            progress = 100

        # storico (se le relazioni sono mappate)
        # carica lazy-safe (puoi ottimizzare quando definisci i modelli collegati)
        return render_template(
            "clienti/me.html",
            cliente=cli,
            qr_url=qr_url,
            prenotazioni_future=prenotazioni_future,
            prenotazioni_passate=prenotazioni_passate,
            ultimo_ingresso=ultimo_ingresso,
            consumi_recenti=consumi_recenti,
            points=points,
            current_level=current_level,
            next_level=nxt,
            to_go=to_go,
            progress=progress
        )
    finally:
        db.close()

@clienti_bp.route("/me/edit", methods=["GET", "POST"])
@require_cliente
def me_edit():
    db = SessionLocal()
    try:
        cli = current_cliente(db)
        if request.method == "GET":
            return render_template("clienti/me_edit.html", cliente=cli)

        # POST: aggiornamento campi consentiti
        cli.telefono = request.form.get("telefono", cli.telefono).strip()
        cli.citta = request.form.get("citta", cli.citta).strip() or None

        # opzionale: cambio password
        new_pass = request.form.get("nuova_password", "").strip()
        if new_pass:
            cli.password_hash = hash_password(new_pass)

        try:
            db.commit()
            flash("✓ Il tuo profilo è stato aggiornato con successo.", "success")
        except IntegrityError:
            db.rollback()
            flash("Questo numero di telefono è già in uso. Prova con un altro.", "warning")
        return redirect(url_for("clienti.area_personale"))
    finally:
        db.close()

# -----------------------
# ADMIN — Dashboard
# -----------------------
@dashboard_bp.route("/admin", methods=["GET"])
@require_admin
def admin_dashboard():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        from app.models.eventi import Evento
        from app.models.ingressi import Ingresso
        from app.models.consumi import Consumo
        from app.models.prenotazioni import Prenotazione
        from app.models.feedback import Feedback
        
        valid_ranges = (7, 30, 90)
        range_days = request.args.get("range", default=30, type=int)
        if range_days not in valid_ranges:
            range_days = 30

        now = datetime.now()
        start_period = now - timedelta(days=range_days)
        prev_period_start = start_period - timedelta(days=range_days)
        prev_period_end = start_period

        # Statistiche clienti aggregate in singola query
        from sqlalchemy import case
        cliente_stats = db.query(
            func.count(Cliente.id_cliente).label('totale'),
            func.sum(case((Cliente.stato_account == 'attivo', 1), else_=0)).label('attivi'),
            func.sum(case((Cliente.data_registrazione >= start_period, 1), else_=0)).label('nuovi'),
            func.sum(case(
                (Cliente.data_registrazione >= prev_period_start, 1),
                else_=0
            ) * case(
                (Cliente.data_registrazione < prev_period_end, 1),
                else_=0
            )).label('nuovi_prev')
        ).one()
        tot_clienti = int(cliente_stats.totale or 0)
        clienti_attivi = int(cliente_stats.attivi or 0)
        nuovi_clienti = int(cliente_stats.nuovi or 0)
        nuovi_clienti_prev = int(cliente_stats.nuovi_prev or 0)
        
        # Eventi
        tot_eventi = db.query(func.count(Evento.id_evento)).scalar() or 0
        eventi_attivi = (
            db.query(func.count(Evento.id_evento))
            .filter(Evento.stato == "attivo")
            .scalar()
            or 0
        )
        prossimo_evento = (
            db.query(Evento)
            .filter(Evento.data_evento >= now.date())
            .order_by(Evento.data_evento.asc())
            .first()
        )
        giorni_al_prossimo_evento = None
        if prossimo_evento and prossimo_evento.data_evento:
            giorni_al_prossimo_evento = (prossimo_evento.data_evento - now.date()).days

        evento_operativo = get_evento_operativo(db)
        prossimo_evento_stats = None
        if prossimo_evento:
            evento_id = prossimo_evento.id_evento
            
            # Query aggregate per statistiche prenotazioni (singola query con CASE)
            pren_stats = db.query(
                func.count(Prenotazione.id_prenotazione).label('totali'),
                func.sum(case((Prenotazione.stato == 'attiva', 1), else_=0)).label('attive'),
                func.sum(case((Prenotazione.stato == 'usata', 1), else_=0)).label('usate')
            ).filter(Prenotazione.evento_id == evento_id).one()
            prenotazioni_totali = int(pren_stats.totali or 0)
            prenotazioni_attive_evento = int(pren_stats.attive or 0)
            prenotazioni_utilizzate = int(pren_stats.usate or 0)
            
            # Query aggregate per ingressi e consumi evento (singola subquery)
            ingressi_tot_evento = (
                db.query(func.count(Ingresso.id_ingresso))
                .filter(Ingresso.evento_id == evento_id)
                .scalar() or 0
            )
            consumi_tot_evento = float(
                db.query(func.coalesce(func.sum(Consumo.importo), 0))
                .filter(Consumo.evento_id == evento_id)
                .scalar() or 0
            )

            # Query feedback evento
            feedback_evento = db.query(
                func.avg(Feedback.voto_musica),
                func.avg(Feedback.voto_ingresso),
                func.avg(Feedback.voto_ambiente),
                func.count(Feedback.id_feedback),
            ).filter(Feedback.evento_id == evento_id).one()
            feedback_samples = int(feedback_evento[3] or 0)
            feedback_media_generale = (
                round(
                    (
                        (feedback_evento[0] or 0)
                        + (feedback_evento[1] or 0)
                        + (feedback_evento[2] or 0)
                    )
                    / 3,
                    1,
                )
                if feedback_samples
                else 0.0
            )

            capienza = prossimo_evento.capienza_max or 0
            occupancy_pct = (
                round(min(100.0, (ingressi_tot_evento / capienza) * 100), 1)
                if capienza
                else 0.0
            )
            booking_load_pct = (
                round(min(100.0, (prenotazioni_attive_evento / capienza) * 100), 1)
                if capienza
                else 0.0
            )
            prossimo_evento_stats = {
                "prenotazioni_totali": prenotazioni_totali,
                "prenotazioni_attive": prenotazioni_attive_evento,
                "prenotazioni_usate": prenotazioni_utilizzate,
                "ingressi_totali": ingressi_tot_evento,
                "consumi_totali": consumi_tot_evento,
                "feedback_samples": feedback_samples,
                "feedback_media_generale": feedback_media_generale,
                "occupancy_pct": occupancy_pct,
                "booking_load_pct": booking_load_pct,
                "capienza": capienza,
            }

        # Query aggregate per ingressi (range + prev in singola query)
        ingressi_stats = db.query(
            func.sum(case((Ingresso.orario_ingresso >= start_period, 1), else_=0)).label('recenti'),
            func.sum(case(
                (Ingresso.orario_ingresso >= prev_period_start, 1),
                else_=0
            ) * case(
                (Ingresso.orario_ingresso < prev_period_end, 1),
                else_=0
            )).label('prev')
        ).one()
        ingressi_recenti = int(ingressi_stats.recenti or 0)
        ingressi_prev = int(ingressi_stats.prev or 0)
        
        # Query aggregate per consumi (range + prev in singola query)
        consumi_stats = db.query(
            func.coalesce(func.sum(case((Consumo.data_consumo >= start_period, Consumo.importo), else_=0)), 0).label('recenti'),
            func.coalesce(func.sum(case(
                (Consumo.data_consumo >= prev_period_start, Consumo.importo),
                else_=0
            ) * case(
                (Consumo.data_consumo < prev_period_end, 1),
                else_=0
            )), 0).label('prev')
        ).one()
        consumi_recenti = float(consumi_stats.recenti or 0)
        consumi_prev = float(consumi_stats.prev or 0)

        # Prenotazioni attive (già efficiente, singola query)
        prenotazioni_attive = (
            db.query(func.count(Prenotazione.id_prenotazione))
            .filter(Prenotazione.stato == "attiva")
            .scalar() or 0
        )
        
        # Feedback (media generale)
        avg_feedback = db.query(
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente),
            func.avg(Feedback.voto_servizio)
        ).one()
        avg_musica = round(avg_feedback[0] or 0, 1)
        avg_ingresso = round(avg_feedback[1] or 0, 1)
        avg_ambiente = round(avg_feedback[2] or 0, 1)
        avg_servizio = round(avg_feedback[3] or 0, 1)
        
        # Distribuzione livelli clienti
        livelli_dist = dict(db.query(Cliente.livello, func.count(Cliente.id_cliente))
                           .group_by(Cliente.livello).all())
        
        # Top clienti per punti
        top_clienti = db.query(Cliente, Cliente.punti_fedelta)\
                       .order_by(Cliente.punti_fedelta.desc())\
                       .limit(5).all()
        
        # Eventi recenti
        eventi_recenti = db.query(Evento)\
                          .order_by(Evento.data_evento.desc())\
                          .limit(5).all()
        
        # Trend temporali per grafici
        date_expr_ingressi = func.date(Ingresso.orario_ingresso)
        ingressi_trend_rows = (
            db.query(
                date_expr_ingressi.label("giorno"),
                func.count(Ingresso.id_ingresso).label("totale")
            )
            .filter(Ingresso.orario_ingresso >= start_period)
            .group_by(date_expr_ingressi)
            .order_by(date_expr_ingressi)
            .all()
        )

        date_expr_consumi = func.date(Consumo.data_consumo)
        consumi_trend_rows = (
            db.query(
                date_expr_consumi.label("giorno"),
                func.coalesce(func.sum(Consumo.importo), 0).label("totale")
            )
            .filter(Consumo.data_consumo >= start_period)
            .group_by(date_expr_consumi)
            .order_by(date_expr_consumi)
            .all()
        )

        start_date = start_period.date()
        end_date = now.date()
        ingressi_trend_map = {}
        for row in ingressi_trend_rows:
            giorno = row.giorno if hasattr(row.giorno, "isoformat") else row[0]
            if hasattr(giorno, "date"):
                giorno = giorno.date()
            ingressi_trend_map[giorno] = int(row.totale or 0)

        consumi_trend_map = {}
        for row in consumi_trend_rows:
            giorno = row.giorno if hasattr(row.giorno, "isoformat") else row[0]
            if hasattr(giorno, "date"):
                giorno = giorno.date()
            consumi_trend_map[giorno] = float(row.totale or 0)

        trend_labels = []
        ingressi_trend_values = []
        consumi_trend_values = []
        cursor = start_date
        while cursor <= end_date:
            trend_labels.append(cursor.strftime("%d/%m"))
            ingressi_trend_values.append(ingressi_trend_map.get(cursor, 0))
            consumi_trend_values.append(round(consumi_trend_map.get(cursor, 0.0), 2))
            cursor += timedelta(days=1)

        def compute_delta(current, previous):
            diff = current - previous
            if previous:
                pct = round((diff / previous) * 100, 1)
            elif current:
                pct = None
            else:
                pct = 0
            return diff, pct

        ingressi_delta_abs, ingressi_delta_pct = compute_delta(ingressi_recenti, ingressi_prev)
        consumi_delta_abs, consumi_delta_pct = compute_delta(consumi_recenti, consumi_prev)
        nuovi_clienti_delta_abs, nuovi_clienti_delta_pct = compute_delta(nuovi_clienti, nuovi_clienti_prev)

        return render_template(
            "admin/dashboard.html",
            tot_clienti=tot_clienti,
            clienti_attivi=clienti_attivi,
            tot_eventi=tot_eventi,
            eventi_attivi=eventi_attivi,
            prossimo_evento=prossimo_evento,
            giorni_al_prossimo_evento=giorni_al_prossimo_evento,
            evento_operativo=evento_operativo,
            prossimo_evento_stats=prossimo_evento_stats,
            ingressi_recenti=ingressi_recenti,
            consumi_recenti=consumi_recenti,
            prenotazioni_attive=prenotazioni_attive,
            nuovi_clienti=nuovi_clienti,
            range_days=range_days,
            range_options=valid_ranges,
            avg_musica=avg_musica,
            avg_ingresso=avg_ingresso,
            avg_ambiente=avg_ambiente,
            avg_servizio=avg_servizio,
            livelli_dist=livelli_dist,
            top_clienti=top_clienti,
            eventi_recenti=eventi_recenti,
            oggi=now.date(),
            ultimo_aggiornamento=now,
            ingressi_delta_abs=ingressi_delta_abs,
            ingressi_delta_pct=ingressi_delta_pct,
            consumi_delta_abs=consumi_delta_abs,
            consumi_delta_pct=consumi_delta_pct,
            nuovi_clienti_delta_abs=nuovi_clienti_delta_abs,
            nuovi_clienti_delta_pct=nuovi_clienti_delta_pct,
            trend_labels=trend_labels,
            ingressi_trend_values=ingressi_trend_values,
            consumi_trend_values=consumi_trend_values
        )
    finally:
        db.close()


@dashboard_bp.route("/admin/statistiche", methods=["GET"])
@require_admin
def admin_statistics():
    db = SessionLocal()
    try:
        from app.models.eventi import Evento
        from app.models.ingressi import Ingresso
        from app.models.consumi import Consumo
        from app.models.prenotazioni import Prenotazione
        from app.models.feedback import Feedback

        valid_ranges = (30, 60, 90, 120)
        range_days = request.args.get("range", default=30, type=int)
        if range_days not in valid_ranges:
            range_days = 30

        now = datetime.utcnow()
        start_period = now - timedelta(days=range_days)
        prev_period_start = start_period - timedelta(days=range_days)
        prev_period_end = start_period

        def compute_delta(current, previous):
            diff = current - previous
            if previous:
                pct = round((diff / previous) * 100, 1)
            elif current:
                pct = None
            else:
                pct = 0
            return diff, pct

        tot_ingressi = db.query(func.count(Ingresso.id_ingresso)).scalar() or 0
        ingressi_range = (
            db.query(func.count(Ingresso.id_ingresso))
            .filter(Ingresso.orario_ingresso >= start_period)
            .scalar()
            or 0
        )
        ingressi_prev = (
            db.query(func.count(Ingresso.id_ingresso))
            .filter(Ingresso.orario_ingresso >= prev_period_start)
            .filter(Ingresso.orario_ingresso < prev_period_end)
            .scalar()
            or 0
        )
        ingressi_delta_abs, ingressi_delta_pct = compute_delta(ingressi_range, ingressi_prev)

        tot_prenotazioni = db.query(func.count(Prenotazione.id_prenotazione)).scalar() or 0
        tot_consumi = db.query(func.coalesce(func.sum(Consumo.importo), 0)).scalar() or 0
        consumi_range = (
            db.query(func.coalesce(func.sum(Consumo.importo), 0))
            .filter(Consumo.data_consumo >= start_period)
            .scalar()
            or 0
        )
        consumi_range = float(consumi_range or 0)
        consumi_prev = (
            db.query(func.coalesce(func.sum(Consumo.importo), 0))
            .filter(Consumo.data_consumo >= prev_period_start)
            .filter(Consumo.data_consumo < prev_period_end)
            .scalar()
            or 0
        )
        consumi_prev = float(consumi_prev or 0)
        consumi_delta_abs, consumi_delta_pct = compute_delta(consumi_range, consumi_prev)

        feedback_global = db.query(
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente),
            func.count(Feedback.id_feedback)
        ).one()
        feedback_global_data = None
        if feedback_global and feedback_global[3]:
            componenti = [
                float(feedback_global[0] or 0),
                float(feedback_global[1] or 0),
                float(feedback_global[2] or 0),
            ]
            feedback_global_data = {
                "labels": ["Musica", "Ingresso", "Ambiente"],
                "values": componenti,
                "average": sum(componenti) / len(componenti) if componenti else 0.0,
                "samples": int(feedback_global[3]),
            }

        feedback_recent = db.query(
            func.count(Feedback.id_feedback),
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente),
        ).filter(Feedback.data_feedback >= start_period).one()
        feedback_range_count = int(feedback_recent[0] or 0)
        feedback_range_avg = None
        if feedback_range_count:
            avg_components = [
                float(feedback_recent[1] or 0),
                float(feedback_recent[2] or 0),
                float(feedback_recent[3] or 0),
            ]
            feedback_range_avg = round(sum(avg_components) / len(avg_components), 1)
        feedback_prev_count = (
            db.query(func.count(Feedback.id_feedback))
            .filter(Feedback.data_feedback >= prev_period_start)
            .filter(Feedback.data_feedback < prev_period_end)
            .scalar()
            or 0
        )
        feedback_delta_abs, feedback_delta_pct = compute_delta(feedback_range_count, feedback_prev_count)

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

        feedback_per_evento_rows = (
            db.query(
                Evento.nome_evento,
                Evento.categoria,
                func.avg(Feedback.voto_musica).label("avg_musica"),
                func.avg(Feedback.voto_ingresso).label("avg_ingresso"),
                func.avg(Feedback.voto_ambiente).label("avg_ambiente"),
                func.count(Feedback.id_feedback).label("tot_feedback")
            )
            .join(Evento, Evento.id_evento == Feedback.evento_id)
            .group_by(Evento.id_evento, Evento.nome_evento, Evento.categoria)
            .having(func.count(Feedback.id_feedback) > 0)
            .order_by(func.count(Feedback.id_feedback).desc())
            .limit(20)
            .all()
        )
        feedback_per_evento_items = []
        max_feedback_samples = 0
        for row in feedback_per_evento_rows:
            samples = int(row.tot_feedback or 0)
            max_feedback_samples = max(max_feedback_samples, samples)
            categoria = row.categoria or "non specificato"
            overall = (
                float(row.avg_musica or 0)
                + float(row.avg_ingresso or 0)
                + float(row.avg_ambiente or 0)
            ) / 3
            feedback_per_evento_items.append({
                "label": row.nome_evento,
                "overall": round(overall, 2),
                "samples": samples,
                "categoria": categoria,
            })
        feedback_per_evento = {
            "items": feedback_per_evento_items,
            "max_samples": max_feedback_samples,
        }

        max_range_days = max(valid_ranges)
        temporal_start = now - timedelta(days=max_range_days)
        date_expr = func.date(Ingresso.orario_ingresso)
        ingressi_temporali_rows = (
            db.query(
                date_expr.label("giorno"),
                func.count(Ingresso.id_ingresso).label("tot_slot")
            )
            .filter(Ingresso.orario_ingresso >= temporal_start)
            .group_by(date_expr)
            .order_by(date_expr)
            .all()
        )
        ingressi_temporali_points = []
        for row in ingressi_temporali_rows:
            giorno = row.giorno
            label = giorno.strftime("%d/%m/%Y") if hasattr(giorno, "strftime") else str(giorno)
            ingressi_temporali_points.append({
                "date": giorno.isoformat() if hasattr(giorno, "isoformat") else str(giorno),
                "label": label,
                "value": int(row.tot_slot or 0),
            })
        ingressi_temporali = {
            "points": ingressi_temporali_points,
            "default_range_days": range_days,
        }

        prodotti_top_rows = (
            db.query(
                Consumo.prodotto,
                func.count(Consumo.id_consumo).label("quantita"),
                func.coalesce(func.sum(Consumo.importo), 0).label("ricavi")
            )
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

        ricavi_per_evento_rows = (
            db.query(
                Evento.nome_evento,
                Evento.categoria,
                func.coalesce(func.sum(Consumo.importo), 0).label("ricavi_evento")
            )
            .join(Evento, Evento.id_evento == Consumo.evento_id)
            .group_by(Evento.id_evento, Evento.nome_evento, Evento.categoria)
            .order_by(func.coalesce(func.sum(Consumo.importo), 0).desc())
            .limit(20)
            .all()
        )
        ricavi_per_evento_items = []
        ricavi_categories = set()
        for row in ricavi_per_evento_rows:
            categoria = row.categoria or "non specificato"
            ricavi_categories.add(categoria)
            ricavi_per_evento_items.append({
                "label": row.nome_evento,
                "value": float(row.ricavi_evento or 0),
                "categoria": categoria,
            })
        ricavi_per_evento = {
            "items": ricavi_per_evento_items,
            "categories": sorted(ricavi_categories),
        }

        prenotazioni_per_tipo_rows = (
            db.query(
                Prenotazione.tipo,
                func.count(Prenotazione.id_prenotazione).label("totale")
            )
            .group_by(Prenotazione.tipo)
            .all()
        )
        prenotazioni_per_tipo = {
            "items": [
                {
                    "label": row.tipo or "non specificato",
                    "value": int(row.totale or 0),
                }
                for row in prenotazioni_per_tipo_rows
            ]
        }

        event_categories = db.query(Evento.categoria).distinct().all()
        event_categories = sorted({row[0] or "non specificato" for row in event_categories})

        top_ingressi_event = ingressi_per_evento_items[0] if ingressi_per_evento_items else None
        top_feedback_event = None
        if feedback_per_evento_items:
            top_feedback_event = max(feedback_per_evento_items, key=lambda item: item["overall"])
        top_ricavi_event = ricavi_per_evento_items[0] if ricavi_per_evento_items else None
        top_prodotto = prodotti_top_items[0] if prodotti_top_items else None

        return render_template(
            "admin/analytics/overview.html",
            tot_ingressi=tot_ingressi,
            tot_prenotazioni=tot_prenotazioni,
            tot_consumi=float(tot_consumi or 0),
            feedback_global=feedback_global_data,
            ingressi_per_evento=ingressi_per_evento,
            feedback_per_evento=feedback_per_evento,
            ingressi_temporali=ingressi_temporali,
            prodotti_top=prodotti_top,
            ricavi_per_evento=ricavi_per_evento,
            prenotazioni_per_tipo=prenotazioni_per_tipo,
            range_days=range_days,
            event_categories=event_categories,
            range_options=valid_ranges,
            ingressi_range=ingressi_range,
            ingressi_delta_abs=ingressi_delta_abs,
            ingressi_delta_pct=ingressi_delta_pct,
            consumi_range=consumi_range,
            consumi_delta_abs=consumi_delta_abs,
            consumi_delta_pct=consumi_delta_pct,
            feedback_range_count=feedback_range_count,
            feedback_range_avg=feedback_range_avg,
            feedback_delta_abs=feedback_delta_abs,
            feedback_delta_pct=feedback_delta_pct,
            top_ingressi_event=top_ingressi_event,
            top_feedback_event=top_feedback_event,
            top_ricavi_event=top_ricavi_event,
            top_prodotto=top_prodotto,
            analytics_generated_at=now,
        )
    finally:
        db.close()

@clienti_bp.route("/admin", methods=["GET"])
@require_admin
def admin_dashboard_legacy():
    """Mantiene la vecchia URL /clienti/admin reindirizzando alla nuova dashboard."""
    return redirect(url_for("dashboard.admin_dashboard"), code=301)

# -----------------------
# ADMIN — Lista clienti
# -----------------------
@clienti_bp.route("/admin/list", methods=["GET"])
@require_admin
def admin_lista_clienti():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Parametri paginazione
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 10), 200)  # Limite tra 10 e 200
        
        # Filtri
        search = request.args.get("q", "").strip()
        stato = request.args.get("stato")  # 'attivo'/'disattivato'/None
        livello = request.args.get("livello")  # 'base'/'loyal'/'premium'/'vip'/None
        
        # Query base
        q = db.query(Cliente)
        
        # Applica filtri
        if search:
            q = q.filter(
                (Cliente.nome.ilike(f"%{search}%")) |
                (Cliente.cognome.ilike(f"%{search}%")) |
                (Cliente.telefono.ilike(f"%{search}%"))
            )
        if stato in ("attivo", "disattivato"):
            q = q.filter(Cliente.stato_account == stato)
        if livello in ("base", "loyal", "premium", "vip"):
            q = q.filter(Cliente.livello == livello)
        
        # Conta totale risultati
        total = q.count()
        
        # Applica paginazione
        clienti = q.order_by(Cliente.id_cliente.desc())\
                   .offset((page - 1) * per_page)\
                   .limit(per_page)\
                   .all()
        
        # Calcola statistiche totali (solo se non ci sono filtri per performance)
        stats = None
        if not search and not stato and not livello:
            stats = {
                'total': db.query(func.count(Cliente.id_cliente)).scalar() or 0,
                'attivi': db.query(func.count(Cliente.id_cliente)).filter(Cliente.stato_account == 'attivo').scalar() or 0,
                'disattivati': db.query(func.count(Cliente.id_cliente)).filter(Cliente.stato_account == 'disattivato').scalar() or 0,
            }
        
        cliente_ids = [c.id_cliente for c in clienti]
        ultimo_ingressi = {}
        if cliente_ids:
            ultime_date = (
                db.query(Ingresso.cliente_id, func.max(Ingresso.orario_ingresso))
                .filter(Ingresso.cliente_id.in_(cliente_ids))
                .group_by(Ingresso.cliente_id)
                .all()
            )
            ultimo_ingressi = {cid: data for cid, data in ultime_date}
        
        # Calcola numero di pagine
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        # Calcola range pagine da mostrare (max 5 pagine intorno alla corrente)
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))
        
        return render_template("admin/clienti_list.html", 
                             clienti=clienti, 
                             search=search,
                             stato=stato,
                             livello=livello,
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages,
                             pages_list=pages_list,
                             stats=stats,
                             ultimo_ingressi=ultimo_ingressi)
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>", methods=["GET"])
@require_admin
def admin_cliente_detail(cliente_id):
    db = SessionLocal()
    try:
        from sqlalchemy import func
        from app.models.prenotazioni import Prenotazione
        from app.models.ingressi import Ingresso
        from app.models.consumi import Consumo
        from app.models.fedeltà import Fedelta
        from app.models.feedback import Feedback
        from app.models.eventi import Evento
        from app.models.promozioni import Promozione, ClientePromozione
        
        cli = db.query(Cliente).get(cliente_id)
        if not cli:
            flash("Cliente non trovato. Potrebbe essere stato rimosso o l'ID non è valido.", "warning")
            return redirect(url_for("clienti.admin_lista_clienti"))
        
        # Statistiche cliente
        tot_prenotazioni = db.query(func.count(Prenotazione.id_prenotazione)).filter(Prenotazione.cliente_id == cliente_id).scalar() or 0
        tot_ingressi = db.query(func.count(Ingresso.id_ingresso)).filter(Ingresso.cliente_id == cliente_id).scalar() or 0
        tot_consumi = db.query(func.sum(Consumo.importo)).filter(Consumo.cliente_id == cliente_id).scalar() or 0
        tot_consumi = float(tot_consumi) if tot_consumi else 0
        tot_punti = db.query(func.sum(Fedelta.punti)).filter(Fedelta.cliente_id == cliente_id).scalar() or 0
        
        # Ultime attività
        ultime_prenotazioni = (
            db.query(Prenotazione, Evento)
            .join(Evento, Evento.id_evento == Prenotazione.evento_id)
            .filter(Prenotazione.cliente_id == cliente_id)
            .order_by(Prenotazione.id_prenotazione.desc())
            .limit(5)
            .all()
        )
        
        ultimi_ingressi = (
            db.query(Ingresso, Evento)
            .join(Evento, Evento.id_evento == Ingresso.evento_id)
            .filter(Ingresso.cliente_id == cliente_id)
            .order_by(Ingresso.orario_ingresso.desc())
            .limit(5)
            .all()
        )
        
        ultimi_consumi = (
            db.query(Consumo, Evento)
            .join(Evento, Evento.id_evento == Consumo.evento_id)
            .filter(Consumo.cliente_id == cliente_id)
            .order_by(Consumo.data_consumo.desc())
            .limit(5)
            .all()
        )
        
        movimenti_fedelta = db.query(Fedelta, Evento)\
                             .join(Evento, Evento.id_evento == Fedelta.evento_id)\
                             .filter(Fedelta.cliente_id == cliente_id)\
                             .order_by(Fedelta.data_assegnazione.desc())\
                             .limit(10).all()
        
        feedback_list = db.query(Feedback, Evento)\
                         .join(Evento, Evento.id_evento == Feedback.evento_id)\
                         .filter(Feedback.cliente_id == cliente_id)\
                         .order_by(Feedback.data_feedback.desc())\
                         .limit(5).all()
        
        # Promozioni del cliente
        promozioni_cliente = db.query(ClientePromozione, Promozione)\
                              .join(Promozione, Promozione.id_promozione == ClientePromozione.promozione_id)\
                              .filter(ClientePromozione.cliente_id == cliente_id)\
                              .order_by(ClientePromozione.data_assegnazione.desc())\
                              .all()
        
        # Promozioni disponibili per assegnare
        promozioni_disponibili = db.query(Promozione)\
                                   .filter(Promozione.attiva == True)\
                                   .filter(
                                       (Promozione.data_inizio.is_(None)) | (Promozione.data_inizio <= date.today()),
                                       (Promozione.data_fine.is_(None)) | (Promozione.data_fine >= date.today())
                                   ).all()
        
        # Filtra quelle già assegnate
        promozioni_assegnate_ids = [cp.promozione_id for cp, _ in promozioni_cliente]
        promozioni_disponibili = [p for p in promozioni_disponibili if p.id_promozione not in promozioni_assegnate_ids]
        
        ultimo_ingresso = None
        if ultimi_ingressi:
            ingresso, evento = ultimi_ingressi[0]
            ultimo_ingresso = {"ingresso": ingresso, "evento": evento}

        ultima_prenotazione = None
        if ultime_prenotazioni:
            prenotazione, evento = ultime_prenotazioni[0]
            ultima_prenotazione = {"prenotazione": prenotazione, "evento": evento}

        ultimo_consumo = None
        if ultimi_consumi:
            consumo, evento = ultimi_consumi[0]
            ultimo_consumo = {"consumo": consumo, "evento": evento}
        
        return render_template(
            "admin/cliente_detail.html",
                             cliente=cli,
                             tot_prenotazioni=tot_prenotazioni,
                             tot_ingressi=tot_ingressi,
                             tot_consumi=tot_consumi,
                             tot_punti=tot_punti,
                             ultime_prenotazioni=ultime_prenotazioni,
                             ultimi_ingressi=ultimi_ingressi,
                             ultimi_consumi=ultimi_consumi,
                             movimenti_fedelta=movimenti_fedelta,
                             feedback_list=feedback_list,
                             promozioni_cliente=promozioni_cliente,
                             promozioni_disponibili=promozioni_disponibili,
            oggi=date.today(),
            ultimo_ingresso=ultimo_ingresso,
            ultima_prenotazione=ultima_prenotazione,
            ultimo_consumo=ultimo_consumo,
        )
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/set-level", methods=["POST"])
@require_admin
def admin_set_level(cliente_id):
    livello = request.form.get("livello")
    if livello not in ("base", "loyal", "premium", "vip"):
        abort(400)
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli: abort(404)
        cli.livello = livello
        db.commit()
        flash("✓ Livello cliente aggiornato con successo.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/adjust-points", methods=["POST"])
@require_admin
def admin_adjust_points(cliente_id):
    delta = int(request.form.get("delta", "0"))
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli: abort(404)
        cli.punti_fedelta = max(0, (cli.punti_fedelta or 0) + delta)
        db.commit()
        flash("✓ Punti fedeltà aggiornati con successo.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/deactivate", methods=["POST"])
@require_admin
def admin_deactivate(cliente_id):
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli: abort(404)
        db.delete(cli)
        db.commit()
        flash("Cliente eliminato definitivamente.", "warning")
        return redirect(url_for("clienti.admin_lista_clienti"))
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/activate", methods=["POST"])
@require_admin
def admin_activate(cliente_id):
    db = SessionLocal()
    try:
        # Non più supportato: riattivazione disabilitata, i clienti vengono eliminati
        flash("Operazione non disponibile. I clienti si eliminano definitivamente.", "warning")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/delete", methods=["POST"])
@require_admin
def admin_delete(cliente_id):
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli:
            abort(404)
        db.delete(cli)
        db.commit()
        flash("Cliente eliminato definitivamente.", "warning")
        return redirect(url_for("clienti.admin_lista_clienti"))
    finally:
        db.close()
@clienti_bp.route("/admin/<int:cliente_id>/set-note", methods=["POST"])
@require_admin
def admin_set_note(cliente_id):
    nota = request.form.get("nota_staff", "").strip() or None
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli: abort(404)
        cli.nota_staff = nota
        db.commit()
        flash("✓ Nota amministrativa aggiornata con successo.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()