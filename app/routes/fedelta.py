# app/routes/fedelta.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.utils.decorators import require_cliente, require_admin

# Modelli
from app.models.clienti import Cliente
from app.models.fedeltà import Fedelta
from app.models.eventi import Evento

# (Opzionale) tabella soglie gestita da admin
try:
    from app.models.soglie_fedelta import SogliaFedelta  # livello(str), punti_min(int)
except Exception:
    SogliaFedelta = None

fedelta_bp = Blueprint("fedelta", __name__, url_prefix="/fedelta")

# -----------------------------
# Regole punteggi (helper)
# -----------------------------
PUNTI_INGRESSO = 10
PUNTI_NO_SHOW = -5

def _default_thresholds():
    # fallback se non esiste tabella soglie: base 0, loyal 100, premium 250, vip 500
    return {
        "base": 0,
        "loyal": 100,
        "premium": 250,
        "vip": 500
    }

def get_thresholds(db):
    if SogliaFedelta is None:
        return _default_thresholds()
    rows = db.query(SogliaFedelta).all()
    if not rows:
        return _default_thresholds()
    # livello -> punti_min (ordinati per punti)
    out = {r.livello: int(r.punti_min) for r in rows}
    # assicura chiavi
    for k, v in _default_thresholds().items():
        out.setdefault(k, v)
    return out

def compute_level(points, thresholds):
    # restituisce uno tra base/loyal/premium/vip in base ai punti
    order = sorted(thresholds.items(), key=lambda x: x[1])  # (livello, punti_min) asc
    current = "base"
    for lvl, minp in order:
        if points >= minp:
            current = lvl
    return current

def next_threshold_info(points, thresholds):
    # ritorna (next_level, points_to_go) oppure (None, 0) se già al massimo
    order = sorted(thresholds.items(), key=lambda x: x[1])
    for lvl, minp in order:
        if points < minp:
            return lvl, max(0, minp - points)
    return None, 0

def _update_cliente_level(db, cliente_id):
    cli = db.query(Cliente).get(cliente_id)
    if not cli:
        return
    thr = get_thresholds(db)
    lvl = compute_level(cli.punti_fedelta or 0, thr)
    if cli.livello != lvl:
        cli.livello = lvl
        db.commit()

# ----------------------------------------
# API “servizio” da riusare in altre route
# ----------------------------------------
def award_on_ingresso(db, cliente_id, evento_id):
    # +10 punti
    m = Fedelta(cliente_id=cliente_id, evento_id=evento_id,
                punti=PUNTI_INGRESSO, motivo=f"Ingresso evento #{evento_id}")
    db.add(m)
    # aggiorna saldo cliente
    cli = db.query(Cliente).get(cliente_id)
    cli.punti_fedelta = (cli.punti_fedelta or 0) + PUNTI_INGRESSO
    db.commit()
    _update_cliente_level(db, cliente_id)

def award_on_no_show(db, cliente_id, evento_id):
    # -5 punti per prenotazione senza ingresso
    m = Fedelta(cliente_id=cliente_id, evento_id=evento_id,
                punti=PUNTI_NO_SHOW, motivo=f"No-show evento #{evento_id}")
    db.add(m)
    cli = db.query(Cliente).get(cliente_id)
    cli.punti_fedelta = (cli.punti_fedelta or 0) + PUNTI_NO_SHOW
    db.commit()
    _update_cliente_level(db, cliente_id)

def award_on_consumo(db, cliente_id, evento_id, importo_euro):
    # 1 punto ogni 10€ (arrotondato per difetto)
    if importo_euro is None:
        return
    pts = int(float(importo_euro) // 10.0)
    if pts == 0:
        return
    m = Fedelta(cliente_id=cliente_id, evento_id=evento_id,
                punti=pts, motivo=f"Consumo evento #{evento_id}")
    db.add(m)
    cli = db.query(Cliente).get(cliente_id)
    cli.punti_fedelta = (cli.punti_fedelta or 0) + pts
    db.commit()
    _update_cliente_level(db, cliente_id)

# =========================================
# 👤 Cliente — dashboard punti minimale
# =========================================
@fedelta_bp.route("/mio", methods=["GET"])
@require_cliente
def mio_dashboard():
    db = SessionLocal()
    try:
        cid = session.get("cliente_id")
        cli = db.query(Cliente).get(cid)
        if not cli:
            abort(404)
        thr = get_thresholds(db)
        points = int(cli.punti_fedelta or 0)
        current_level = compute_level(points, thr)
        nxt, to_go = next_threshold_info(points, thr)
        next_points = thr.get(nxt) if nxt else None
        # progress % (verso prossimo livello)
        if nxt:
            prev_min = max([v for k, v in thr.items() if v <= points])
            denom = max(1, next_points - prev_min)
            progress = int(100 * (points - prev_min) / denom)
        else:
            progress = 100
        return render_template("clienti/fedelta_dashboard.html",
                               cliente=cli,
                               points=points,
                               current_level=current_level,
                               next_level=nxt,
                               to_go=to_go,
                               progress=progress)
    finally:
        db.close()

# =========================================
# 🧑‍🍳 Staff — scan QR → mostra saldo/tier
# =========================================
@fedelta_bp.route("/staff/scan", methods=["GET", "POST"])
@require_admin   # placeholder finché non c'è auth staff
def staff_quick():
    db = SessionLocal()
    try:
        info = None
        if request.method == "POST":
            qr = (request.form.get("qr") or "").strip()
            cli = db.query(Cliente).filter(Cliente.qr_code == qr).first()
            if not cli:
                flash("Cliente non trovato con il QR fornito.", "danger")
                return redirect(url_for("fedelta.staff_quick"))
            thr = get_thresholds(db)
            points = int(cli.punti_fedelta or 0)
            lvl = compute_level(points, thr)
            nxt, to_go = next_threshold_info(points, thr)
            info = {"cliente": cli, "points": points, "lvl": lvl, "nxt": nxt, "to_go": to_go}
        return render_template("staff/fedelta_quick.html", info=info)
    finally:
        db.close()

# =========================================
# 👑 Admin — lista & filtri
# =========================================
@fedelta_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        
        # Parametri paginazione
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 10), 200)
        
        # Filtri
        evento_id = request.args.get("evento_id", type=int)
        cliente_q = (request.args.get("q") or "").strip()
        dal = request.args.get("dal")
        al  = request.args.get("al")

        q = db.query(Fedelta, Cliente, Evento).join(Cliente, Cliente.id_cliente == Fedelta.cliente_id)\
                                              .join(Evento, Evento.id_evento == Fedelta.evento_id)
        if evento_id:
            q = q.filter(Fedelta.evento_id == evento_id)
        if cliente_q:
            like = f"%{cliente_q}%"
            q = q.filter((Cliente.nome.ilike(like)) | (Cliente.cognome.ilike(like)) | (Cliente.telefono.ilike(like)))
        if dal:
            try:
                d = datetime.strptime(dal, "%Y-%m-%d")
                q = q.filter(Fedelta.data_assegnazione >= d)
            except ValueError: pass
        if al:
            try:
                d2 = datetime.strptime(al, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(Fedelta.data_assegnazione < d2)
            except ValueError: pass

        # Conta totale
        total = q.count()
        
        # Applica paginazione
        rows = q.order_by(Fedelta.data_assegnazione.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()
        
        # Calcola pagine
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))
        
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        return render_template("admin/fedelta_list.html", 
                             rows=rows, 
                             eventi=eventi,
                             filtro={"evento_id": evento_id, "q": cliente_q, "dal": dal, "al": al},
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages,
                             pages_list=pages_list)
    finally:
        db.close()

# =========================================
# 👑 Admin — nuovo/modifica/elimina (solo manuale)
# =========================================
def _is_manual(mov):
    # se esiste attributo 'tipo', consenti solo 'manuale'
    return (not hasattr(mov, "tipo")) or (getattr(mov, "tipo", "manuale") == "manuale")

@fedelta_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        clienti = db.query(Cliente).order_by(Cliente.cognome.asc(), Cliente.nome.asc()).all()
        if request.method == "POST":
            cliente_id = request.form.get("cliente_id", type=int)
            evento_id = request.form.get("evento_id", type=int)
            punti = request.form.get("punti", type=int)
            motivo = (request.form.get("motivo") or "").strip()
            if not motivo:
                flash("Motivo obbligatorio.", "danger")
                return redirect(url_for("fedelta.admin_new"))
            m = Fedelta(cliente_id=cliente_id, evento_id=evento_id, punti=punti, motivo=motivo)
            # marca manuale se colonna esiste
            if hasattr(Fedelta, "tipo"):
                setattr(m, "tipo", "manuale")
            db.add(m)
            # aggiorna saldo cliente
            cli = db.query(Cliente).get(cliente_id)
            cli.punti_fedelta = (cli.punti_fedelta or 0) + int(punti or 0)
            db.commit()
            _update_cliente_level(db, cliente_id)
            flash("Movimento fedeltà creato.", "success")
            return redirect(url_for("fedelta.admin_list"))
        return render_template("admin/fedelta_form.html", e=None, eventi=eventi, clienti=clienti)
    finally:
        db.close()

@fedelta_bp.route("/admin/<int:mov_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(mov_id):
    db = SessionLocal()
    try:
        m = db.query(Fedelta).get(mov_id)
        if not m:
            flash("Movimento non trovato.", "danger"); return redirect(url_for("fedelta.admin_list"))
        if not _is_manual(m):
            flash("Non è consentito modificare movimenti non manuali.", "warning")
            return redirect(url_for("fedelta.admin_list"))

        if request.method == "POST":
            delta_old = int(m.punti or 0)
            punti = request.form.get("punti", type=int)
            motivo = (request.form.get("motivo") or "").strip()
            if not motivo:
                flash("Motivo obbligatorio.", "danger")
                return redirect(url_for("fedelta.admin_edit", mov_id=mov_id))
            m.punti = int(punti or 0)
            m.motivo = motivo
            # ribilancia saldo cliente
            diff = int(punti or 0) - delta_old
            cli = db.query(Cliente).get(m.cliente_id)
            cli.punti_fedelta = (cli.punti_fedelta or 0) + diff
            db.commit()
            _update_cliente_level(db, m.cliente_id)
            flash("Movimento aggiornato.", "success")
            return redirect(url_for("fedelta.admin_list"))

        return render_template("admin/fedelta_form.html", e=m, eventi=[], clienti=[])
    finally:
        db.close()

@fedelta_bp.route("/admin/<int:mov_id>/delete", methods=["POST"])
@require_admin
def admin_delete(mov_id):
    db = SessionLocal()
    try:
        m = db.query(Fedelta).get(mov_id)
        if m:
            if not _is_manual(m):
                flash("Non è consentito eliminare movimenti non manuali.", "warning")
                return redirect(url_for("fedelta.admin_list"))
            cli = db.query(Cliente).get(m.cliente_id)
            cli.punti_fedelta = (cli.punti_fedelta or 0) - int(m.punti or 0)
            db.delete(m)
            db.commit()
            _update_cliente_level(db, cli.id_cliente)
            flash("Movimento eliminato.", "warning")
        return redirect(url_for("fedelta.admin_list"))
    finally:
        db.close()

# =========================================
# 👑 Admin — analytics (periodo)
# =========================================
@fedelta_bp.route("/admin/analytics", methods=["GET"])
@require_admin
def admin_analytics():
    db = SessionLocal()
    try:
        dal = request.args.get("dal")
        al  = request.args.get("al")
        q = db.query(Fedelta, Cliente).join(Cliente, Cliente.id_cliente == Fedelta.cliente_id)
        if dal:
            try:
                d = datetime.strptime(dal, "%Y-%m-%d")
                q = q.filter(Fedelta.data_assegnazione >= d)
            except ValueError: pass
        if al:
            try:
                d2 = datetime.strptime(al, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(Fedelta.data_assegnazione < d2)
            except ValueError: pass

        # top clienti per periodo
        top = (db.query(Cliente, func.sum(Fedelta.punti).label("pts"))
                 .join(Cliente, Cliente.id_cliente == Fedelta.cliente_id)
                 .group_by(Cliente.id_cliente)
                 .order_by(func.sum(Fedelta.punti).desc())
                 .limit(20).all())

        # distribuzione tier (usa valore corrente nel profilo cliente)
        dist = (db.query(Cliente.livello, func.count(Cliente.id_cliente))
                  .group_by(Cliente.livello).all())
        dist = dict(dist)

        # punti medi per evento nel periodo
        per_evento = dict(db.query(Fedelta.evento_id, func.avg(Fedelta.punti))
                            .group_by(Fedelta.evento_id).all())

        return render_template("admin/fedelta_analytics.html",
                               dal=dal, al=al, top=top, dist=dist, per_evento=per_evento)
    finally:
        db.close()

# =========================================
# 👑 Admin — gestione soglie livelli
# =========================================
@fedelta_bp.route("/admin/soglie", methods=["GET", "POST"])
@require_admin
def admin_soglie():
    db = SessionLocal()
    try:
        if SogliaFedelta is None:
            flash("La gestione soglie richiede la tabella 'soglie_fedelta'. Vedi migrazione SQL suggerita.", "warning")
            return render_template("admin/fedelta_soglie.html", soglie=_default_thresholds(), editable=False)

        if request.method == "POST":
            data = {
                "base": request.form.get("base", type=int),
                "loyal": request.form.get("loyal", type=int),
                "premium": request.form.get("premium", type=int),
                "vip": request.form.get("vip", type=int),
            }
            for lvl, pts in data.items():
                row = db.query(SogliaFedelta).filter(SogliaFedelta.livello == lvl).first()
                if not row:
                    row = SogliaFedelta(livello=lvl, punti_min=pts)
                    db.add(row)
                else:
                    row.punti_min = pts
            db.commit()
            flash("Soglie aggiornate.", "success")
            return redirect(url_for("fedelta.admin_soglie"))

        # GET
        rows = db.query(SogliaFedelta).all()
        soglie = _default_thresholds()
        for r in rows:
            soglie[r.livello] = int(r.punti_min)
        return render_template("admin/fedelta_soglie.html", soglie=soglie, editable=True)
    finally:
        db.close()