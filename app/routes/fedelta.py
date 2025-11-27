# app/routes/fedelta.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.utils.decorators import require_cliente, require_admin, require_staff

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
PUNTI_INGRESSO_PRENOTAZIONE = 10
PUNTI_INGRESSO_LIBERO = 5
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
def award_on_ingresso(db, cliente_id, evento_id, has_prenotazione=False):
    punti = PUNTI_INGRESSO_PRENOTAZIONE if has_prenotazione else PUNTI_INGRESSO_LIBERO
    motivo = (
        f"Ingresso evento #{evento_id} (prenotazione)"
        if has_prenotazione else
        f"Ingresso evento #{evento_id} (walk-in)"
    )
    m = Fedelta(cliente_id=cliente_id, evento_id=evento_id,
                punti=punti, motivo=motivo)
    db.add(m)
    # aggiorna saldo cliente
    cli = db.query(Cliente).get(cliente_id)
    cli.punti_fedelta = (cli.punti_fedelta or 0) + punti
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
    # Reindirizza al profilo, la barra fedeltà è stata spostata lì
    return redirect(url_for("clienti.area_personale"))

# =========================================
# 🧑‍🍳 Staff — scan QR → mostra saldo/tier
# =========================================
@fedelta_bp.route("/staff/scan", methods=["GET", "POST"])
@require_staff
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
@fedelta_bp.route("/admin", methods=["GET", "POST"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        if request.method == "POST":
            if SogliaFedelta is None:
                flash("Per modificare le soglie è necessaria la tabella 'soglie_fedelta'.", "warning")
                return redirect(url_for("fedelta.admin_list"))

            try:
                loyal = request.form.get("loyal", type=int)
                premium = request.form.get("premium", type=int)
                vip = request.form.get("vip", type=int)
            except ValueError:
                loyal = premium = vip = None

            if None in (loyal, premium, vip):
                flash("Inserisci valori numerici validi per le soglie.", "danger")
                return redirect(url_for("fedelta.admin_list"))

            if min(loyal, premium, vip) < 0:
                flash("Le soglie non possono essere negative.", "danger")
                return redirect(url_for("fedelta.admin_list"))

            if not (0 <= loyal <= premium <= vip):
                flash("Le soglie devono essere crescenti (Base 0 ≤ Loyal ≤ Premium ≤ VIP).", "warning")
                return redirect(url_for("fedelta.admin_list"))

            data = {
                "base": 0,
                "loyal": loyal,
                "premium": premium,
                "vip": vip,
            }

            for lvl, pts in data.items():
                row = db.query(SogliaFedelta).filter(SogliaFedelta.livello == lvl).first()
                if not row:
                    row = SogliaFedelta(livello=lvl, punti_min=pts)
                    db.add(row)
                else:
                    row.punti_min = pts
            db.commit()
            flash("Soglie aggiornate correttamente.", "success")
            return redirect(url_for("fedelta.admin_list"))

        thresholds = get_thresholds(db)
        thresholds_sorted = sorted(thresholds.items(), key=lambda x: x[1])

        totale_clienti = db.query(func.count(Cliente.id_cliente)).scalar() or 0
        punti_totali = db.query(func.coalesce(func.sum(Cliente.punti_fedelta), 0)).scalar() or 0
        punti_medi = int(round(punti_totali / totale_clienti)) if totale_clienti else 0

        top_raw = (db.query(Cliente)
                     .order_by(Cliente.punti_fedelta.is_(None).asc(),
                               Cliente.punti_fedelta.desc())
                     .limit(12)
                     .all())
        top_clienti = []
        for cli in top_raw:
            points = int(cli.punti_fedelta or 0)
            level = compute_level(points, thresholds)
            nxt, to_go = next_threshold_info(points, thresholds)
            top_clienti.append({
                "cliente": cli,
                "points": points,
                "level": level,
                "next_level": nxt,
                "points_to_next": to_go
            })

        distribuzione_raw = db.query(Cliente.livello, func.count(Cliente.id_cliente))\
                              .group_by(Cliente.livello).all()
        distribuzione_map = {lvl or "base": count for lvl, count in distribuzione_raw}
        distribuzione = [(lvl, distribuzione_map.get(lvl, 0)) for lvl, _ in thresholds_sorted]

        recent = (db.query(Fedelta, Cliente, Evento)
                    .join(Cliente, Cliente.id_cliente == Fedelta.cliente_id)
                    .join(Evento, Evento.id_evento == Fedelta.evento_id)
                    .order_by(Fedelta.data_assegnazione.desc())
                    .limit(6)
                    .all())
        recent_movimenti = [
            {"movimento": mov, "cliente": cli, "evento": ev}
            for mov, cli, ev in recent
        ]

        stats = {
            "totale_clienti": totale_clienti,
            "punti_totali": int(punti_totali),
            "punti_medi": punti_medi
        }

        return render_template(
            "admin/fedelta_list.html",
            stats=stats,
            top_clienti=top_clienti,
            thresholds=thresholds,
            thresholds_sorted=thresholds_sorted,
            can_edit_thresholds=SogliaFedelta is not None,
            distribuzione=distribuzione,
            recent_movimenti=recent_movimenti
        )
    finally:
        db.close()

# =========================================
# 👑 Admin — elenco movimenti dettagliati
# =========================================
@fedelta_bp.route("/admin/movimenti", methods=["GET"])
@require_admin
def admin_movimenti():
    db = SessionLocal()
    try:
        from sqlalchemy import func

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 10), 200)

        evento_id = request.args.get("evento_id", type=int)
        cliente_q = (request.args.get("q") or "").strip()
        dal = request.args.get("dal")
        al = request.args.get("al")

        q = db.query(Fedelta, Cliente, Evento)\
              .join(Cliente, Cliente.id_cliente == Fedelta.cliente_id)\
              .join(Evento, Evento.id_evento == Fedelta.evento_id)

        if evento_id:
            q = q.filter(Fedelta.evento_id == evento_id)
        if cliente_q:
            like = f"%{cliente_q}%"
            q = q.filter((Cliente.nome.ilike(like)) |
                         (Cliente.cognome.ilike(like)) |
                         (Cliente.telefono.ilike(like)))
        if dal:
            try:
                d = datetime.strptime(dal, "%Y-%m-%d")
                q = q.filter(Fedelta.data_assegnazione >= d)
            except ValueError:
                pass
        if al:
            try:
                d2 = datetime.strptime(al, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(Fedelta.data_assegnazione < d2)
            except ValueError:
                pass

        total = q.count()

        rows = (q.order_by(Fedelta.data_assegnazione.desc())
                  .offset((page - 1) * per_page)
                  .limit(per_page)
                  .all())

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages_list = list(range(start_page, end_page + 1))

        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()

        return render_template(
            "admin/fedelta_movimenti.html",
            rows=rows,
            eventi=eventi,
            filtro={"evento_id": evento_id, "q": cliente_q, "dal": dal, "al": al},
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            pages_list=pages_list
        )
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