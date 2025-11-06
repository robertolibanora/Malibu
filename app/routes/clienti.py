from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.clienti import Cliente
from app.utils.qr import generate_short_code, qr_data_url
from app.utils.decorators import require_cliente, require_admin
from datetime import datetime, date

clienti_bp = Blueprint("clienti", __name__, url_prefix="/clienti")

# -----------------------
# Helpers session utente
# -----------------------
def current_cliente(db):
    """
    Helper per ottenere il cliente attualmente loggato dalla sessione.
    """
    cid = session.get("cliente_id")
    if not cid:
        return None
    return db.query(Cliente).get(cid)

# -----------------------
# REGISTRAZIONE CLIENTE
# -----------------------
@clienti_bp.route("/register", methods=["GET"])
def register_form():
    return render_template("shared/register.html")

@clienti_bp.route("/register", methods=["POST"])
def register_submit():
    nome = request.form.get("nome", "").strip()
    cognome = request.form.get("cognome", "").strip()
    telefono = request.form.get("telefono", "").strip()
    data_nascita = request.form.get("data_nascita")  # yyyy-mm-dd
    citta = request.form.get("citta", "").strip()
    password = request.form.get("password", "").strip()

    if not all([nome, cognome, telefono, password]):
        flash("Compila tutti i campi obbligatori.", "danger")
        return redirect(url_for("clienti.register_form"))

    db = SessionLocal()
    try:
        # genera QR unico
        qr = generate_unique_qr(db)

        nuovo = Cliente(
            nome=nome,
            cognome=cognome,
            telefono=telefono,
            data_nascita=data_nascita if data_nascita else None,
            citta=citta if citta else None,
            password_hash=password,  # TODO: placeholder - implementare hash_password in futuro
            qr_code=qr,
            livello="base",
            punti_fedelta=0,
            stato_account="attivo"
        )
        db.add(nuovo)
        db.flush()  # Per ottenere l'ID del cliente
        
        # Assegna automaticamente le promozioni con auto_assegnazione=True
        from app.models.promozioni import Promozione, ClientePromozione
        from datetime import date
        promozioni_auto = db.query(Promozione).filter(
            Promozione.auto_assegnazione == True,
            Promozione.attiva == True
        ).filter(
            (Promozione.data_inizio.is_(None)) | (Promozione.data_inizio <= date.today()),
            (Promozione.data_fine.is_(None)) | (Promozione.data_fine >= date.today())
        ).all()
        
        for prom in promozioni_auto:
            # Verifica condizioni (livello e punti)
            if prom.livello_richiesto and nuovo.livello != prom.livello_richiesto:
                continue
            if prom.punti_richiesti and (nuovo.punti_fedelta or 0) < prom.punti_richiesti:
                continue
            
            cp = ClientePromozione(
                cliente_id=nuovo.id_cliente,
                promozione_id=prom.id_promozione,
                data_scadenza=prom.data_fine
            )
            db.add(cp)
        
        db.commit()
        session["cliente_id"] = nuovo.id_cliente
        flash("Registrazione completata!", "success")
        return redirect(url_for("clienti.area_personale"))
    except IntegrityError:
        db.rollback()
        # blocco duplicati su telefono -> 409
        flash("Telefono già registrato. Se è tuo, prova il login.", "warning")
        return redirect(url_for("clienti.register_form"))
    finally:
        db.close()

def generate_unique_qr(db) -> str:
    # loop fino a trovare un codice libero
    while True:
        code = generate_short_code(10)
        if not db.query(Cliente).filter_by(qr_code=code).first():
            return code

# -----------------------
# LOGIN / LOGOUT
# -----------------------
@clienti_bp.route("/login", methods=["GET", "POST"])
def login_form():
    # Redirect alla route unificata in auth
    if request.method == "POST":
        return redirect(url_for("auth.auth_login_submit"), code=307)  # 307 mantiene il metodo POST
    return redirect(url_for("auth.auth_login_form"))

@clienti_bp.route("/logout")
def logout():
    # Usa il logout unificato in auth
    return redirect(url_for("auth.logout"))

# -----------------------
# AREA PERSONALE CLIENTE
# -----------------------
@clienti_bp.route("/me", methods=["GET"])
@require_cliente
def area_personale():
    db = SessionLocal()
    try:
        cli = current_cliente(db)
        # Prepara QR in data URL per embed
        qr_url = qr_data_url(cli.qr_code) if cli and cli.qr_code else None

        # storico (se le relazioni sono mappate)
        # carica lazy-safe (puoi ottimizzare quando definisci i modelli collegati)
        return render_template(
            "clienti/me.html",
            cliente=cli,
            qr_url=qr_url
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
        cli.data_nascita = request.form.get("data_nascita") or None

        # opzionale: cambio password
        new_pass = request.form.get("nuova_password", "").strip()
        if new_pass:
            cli.password_hash = new_pass  # TODO: placeholder - implementare hash_password in futuro

        try:
            db.commit()
            flash("Profilo aggiornato.", "success")
        except IntegrityError:
            db.rollback()
            flash("Telefono già in uso.", "danger")
        return redirect(url_for("clienti.me_edit"))
    finally:
        db.close()

# -----------------------
# ADMIN — Dashboard
# -----------------------
@clienti_bp.route("/admin", methods=["GET"])
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
        
        # Statistiche generali
        tot_clienti = db.query(func.count(Cliente.id_cliente)).scalar() or 0
        clienti_attivi = db.query(func.count(Cliente.id_cliente)).filter(Cliente.stato_account == "attivo").scalar() or 0
        
        # Eventi
        tot_eventi = db.query(func.count(Evento.id_evento)).scalar() or 0
        eventi_attivi = db.query(func.count(Evento.id_evento)).filter(Evento.stato == "attivo").scalar() or 0
        prossimo_evento = db.query(Evento).filter(Evento.data_evento >= datetime.now().date()).order_by(Evento.data_evento.asc()).first()
        
        # Ingressi (ultimi 30 giorni)
        trenta_giorni_fa = datetime.now() - timedelta(days=30)
        ingressi_recenti = db.query(func.count(Ingresso.id_ingresso)).filter(Ingresso.orario_ingresso >= trenta_giorni_fa).scalar() or 0
        
        # Consumi (ultimi 30 giorni)
        consumi_recenti = db.query(func.sum(Consumo.importo)).filter(Consumo.data_consumo >= trenta_giorni_fa).scalar() or 0
        consumi_recenti = float(consumi_recenti) if consumi_recenti else 0
        
        # Prenotazioni (ultimi 30 giorni)
        prenotazioni_recenti = db.query(func.count(Prenotazione.id_prenotazione)).filter(Prenotazione.stato == "attiva").scalar() or 0
        
        # Feedback (media generale)
        avg_feedback = db.query(
            func.avg(Feedback.voto_musica),
            func.avg(Feedback.voto_ingresso),
            func.avg(Feedback.voto_ambiente)
        ).one()
        avg_musica = round(avg_feedback[0] or 0, 1)
        avg_ingresso = round(avg_feedback[1] or 0, 1)
        avg_ambiente = round(avg_feedback[2] or 0, 1)
        
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
        
        return render_template("admin/dashboard.html",
                             tot_clienti=tot_clienti,
                             clienti_attivi=clienti_attivi,
                             tot_eventi=tot_eventi,
                             eventi_attivi=eventi_attivi,
                             prossimo_evento=prossimo_evento,
                             ingressi_recenti=ingressi_recenti,
                             consumi_recenti=consumi_recenti,
                             prenotazioni_recenti=prenotazioni_recenti,
                             avg_musica=avg_musica,
                             avg_ingresso=avg_ingresso,
                             avg_ambiente=avg_ambiente,
                             livelli_dist=livelli_dist,
                             top_clienti=top_clienti,
                             eventi_recenti=eventi_recenti)
    finally:
        db.close()

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
                             stats=stats)
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
            flash("Cliente non trovato.", "danger")
            return redirect(url_for("clienti.admin_lista_clienti"))
        
        # Statistiche cliente
        tot_prenotazioni = db.query(func.count(Prenotazione.id_prenotazione)).filter(Prenotazione.cliente_id == cliente_id).scalar() or 0
        tot_ingressi = db.query(func.count(Ingresso.id_ingresso)).filter(Ingresso.cliente_id == cliente_id).scalar() or 0
        tot_consumi = db.query(func.sum(Consumo.importo)).filter(Consumo.cliente_id == cliente_id).scalar() or 0
        tot_consumi = float(tot_consumi) if tot_consumi else 0
        tot_punti = db.query(func.sum(Fedelta.punti)).filter(Fedelta.cliente_id == cliente_id).scalar() or 0
        
        # Ultime attività
        ultime_prenotazioni = db.query(Prenotazione, Evento)\
                               .join(Evento, Evento.id_evento == Prenotazione.evento_id)\
                               .filter(Prenotazione.cliente_id == cliente_id)\
                               .order_by(Prenotazione.id_prenotazione.desc())\
                               .limit(5).all()
        
        ultimi_ingressi = db.query(Ingresso, Evento)\
                           .join(Evento, Evento.id_evento == Ingresso.evento_id)\
                           .filter(Ingresso.cliente_id == cliente_id)\
                           .order_by(Ingresso.orario_ingresso.desc())\
                           .limit(5).all()
        
        ultimi_consumi = db.query(Consumo, Evento)\
                          .join(Evento, Evento.id_evento == Consumo.evento_id)\
                          .filter(Consumo.cliente_id == cliente_id)\
                          .order_by(Consumo.data_consumo.desc())\
                          .limit(5).all()
        
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
        
        return render_template("admin/cliente_detail.html",
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
                             oggi=date.today())
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
        flash("Livello aggiornato.", "success")
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
        flash("Punti aggiornati.", "success")
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
        cli.stato_account = "disattivato"
        db.commit()
        flash("Account disattivato.", "warning")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

@clienti_bp.route("/admin/<int:cliente_id>/activate", methods=["POST"])
@require_admin
def admin_activate(cliente_id):
    db = SessionLocal()
    try:
        cli = db.query(Cliente).get(cliente_id)
        if not cli: abort(404)
        cli.stato_account = "attivo"
        db.commit()
        flash("Account riattivato.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
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
        flash("Nota aggiornata.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()