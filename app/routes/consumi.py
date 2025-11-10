# app/routes/consumi.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, current_app
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.utils.decorators import require_cliente, require_admin, require_staff
from app.routes.log_attivita import log_action
from app.utils.events import get_evento_operativo

from app.models.clienti import Cliente
from app.models.eventi import Evento
from app.models.ingressi import Ingresso
from app.models.consumi import Consumo
from app.models.staff import Staff
from app.routes.fedelta import award_on_consumo

# Supporto opzionale catalogo prodotti (se esiste il modello)
try:
    from app.models.prodotti import Prodotto  # tabella opzionale
except Exception:
    Prodotto = None

consumi_bp = Blueprint("consumi", __name__, url_prefix="/consumi")

PUNTI = ("tavolo", "privè")
# --------------------------------
# Helpers comuni
# --------------------------------
def _get_evento_attivo(db):
    return get_evento_operativo(db)

def _get_staff_id():
    return session.get("staff_id")

def _cliente_by_qr(db, qr):
    if not qr:
        return None
    return db.query(Cliente).filter(Cliente.qr_code == qr.strip()).first()

def _cliente_has_ingresso(db, cliente_id, evento_id):
    return db.query(Ingresso.id_ingresso).filter(
        Ingresso.cliente_id == cliente_id,
        Ingresso.evento_id == evento_id
    ).first() is not None

# ============================================
# 👤 CLIENTE — Storico consumi
# ============================================
@consumi_bp.route("/miei", methods=["GET"])
@require_cliente
def miei():
    db = SessionLocal()
    try:
        cid = session.get("cliente_id")
        rows = (db.query(Consumo, Evento)
                  .join(Evento, Evento.id_evento == Consumo.evento_id)
                  .filter(Consumo.cliente_id == cid)
                  .order_by(Consumo.data_consumo.desc())
                  .all())
        # Totali per evento
        per_evento = dict(db.query(Consumo.evento_id, func.sum(Consumo.importo))
                            .filter(Consumo.cliente_id == cid)
                            .group_by(Consumo.evento_id).all())
        totale = db.query(func.sum(Consumo.importo)).filter(Consumo.cliente_id == cid).scalar() or 0
        return render_template("clienti/consumi_list.html",
                               rows=rows, per_evento=per_evento, totale=totale)
    finally:
        db.close()

# ============================================
# 🧑‍🍳 STAFF — Listino prodotti e addebito QR
# ============================================
@consumi_bp.route("/staff/listino", methods=["GET"])
@require_staff
def staff_listino():
    """Visualizza il listino prodotti per lo staff"""
    db = SessionLocal()
    try:
        e = _get_evento_attivo(db)
        if not e:
            flash("Nessun evento attivo impostato. Contatta un amministratore.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        if e.stato_pubblico == "chiuso" or not e.is_staff_operativo:
            flash("Evento non operativo o chiuso. Imposta un evento operativo prima di registrare consumi.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        
        # Carica prodotti attivi raggruppati per categoria
        prodotti = []
        if Prodotto is not None:
            prodotti = db.query(Prodotto).filter(Prodotto.attivo == True).order_by(Prodotto.categoria.asc(), Prodotto.nome.asc()).all()
        
        # Raggruppa per categoria
        prodotti_per_categoria = {}
        for p in prodotti:
            categoria = p.categoria or "Altro"
            if categoria not in prodotti_per_categoria:
                prodotti_per_categoria[categoria] = []
            prodotti_per_categoria[categoria].append(p)
        
        return render_template("staff/listino.html", 
                             evento=e, 
                             prodotti_per_categoria=prodotti_per_categoria,
                             prodotti=prodotti)
    finally:
        db.close()


@consumi_bp.route("/staff/listino/addebito", methods=["POST"])
@require_staff
def staff_listino_addebito():
    """Processa l'addebito di prodotti selezionati al QR code del cliente"""
    db = SessionLocal()
    try:
        e = _get_evento_attivo(db)
        if not e:
            flash("Nessun evento attivo impostato. Contatta un amministratore.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        if e.stato_pubblico == "chiuso" or not e.is_staff_operativo:
            flash("Evento non operativo o chiuso. Imposta un evento operativo prima di registrare consumi.", "warning")
            return redirect(url_for("eventi.staff_select_event"))
        
        qr = (request.form.get("qr") or "").strip()
        cli = _cliente_by_qr(db, qr)
        if not cli:
            flash("QR non valido o cliente non trovato.", "danger")
            return redirect(url_for("consumi.staff_listino"))
        
        # Controllo ingresso -> solo warning
        if not _cliente_has_ingresso(db, cli.id_cliente, e.id_evento):
            flash("Attenzione: cliente non risulta entrato a questo evento.", "warning")
        
        # Recupera prodotti selezionati
        prodotti_selezionati = request.form.getlist("prodotto_id")
        quantita = {}
        for pid in prodotti_selezionati:
            qty = request.form.get(f"quantita_{pid}", type=int, default=1)
            if qty and qty > 0:
                quantita[int(pid)] = qty
        
        if not quantita:
            flash("Seleziona almeno un prodotto.", "danger")
            return redirect(url_for("consumi.staff_listino"))
        
        # Recupera altri parametri
        punto_vendita = request.form.get("punto_vendita", "bar")
        note = (request.form.get("note") or "").strip() or None
        
        if punto_vendita in PUNTI and not note:
            flash("Per tavolo/privè è obbligatoria una nota (es. Tavolo 7).", "danger")
            return redirect(url_for("consumi.staff_listino"))
        
        # Crea consumi per ogni prodotto selezionato
        totale_importo = 0
        consumi_creati = []
        
        for pid, qty in quantita.items():
            if Prodotto is None:
                continue
            p = db.query(Prodotto).get(pid)
            if not p or not p.attivo:
                continue
            
            importo_totale = float(p.prezzo) * qty
            totale_importo += importo_totale
            
            # Crea un consumo per ogni quantità (o un unico consumo con quantità nel nome)
            nome_prodotto = f"{p.nome}" + (f" x{qty}" if qty > 1 else "")
            
            c = Consumo(
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                staff_id=_get_staff_id(),
                prodotto_id=pid,
                prodotto=nome_prodotto,
                importo=importo_totale,
                punto_vendita=punto_vendita,
                note=note
            )
            db.add(c)
            db.flush()  # assicura id_consumo disponibile
            log_action(db, tabella="consumi", record_id=c.id_consumo, staff_id=_get_staff_id(), azione="insert")
            consumi_creati.append(c)
        
        db.commit()
        
        # Assegna punti fedeltà basati sul totale
        if totale_importo > 0:
            award_on_consumo(db, cliente_id=cli.id_cliente, evento_id=e.id_evento, importo_euro=totale_importo)
        
        flash(f"Addebito completato! Totale: €{totale_importo:.2f}. Punti assegnati: {int(totale_importo // 10)}", "success")
        return redirect(url_for("consumi.staff_listino"))
    finally:
        db.close()


# ============================================
# 🧑‍🍳 STAFF — Nuovo consumo (QR + evento attivo)
# ============================================
@consumi_bp.route("/staff/new", methods=["GET", "POST"])
@require_staff
def staff_new():
    db = SessionLocal()
    try:
        e = _get_evento_attivo(db)
        if not e:
            flash("Nessun evento attivo impostato. Contatta un amministratore.", "warning")
            return redirect(url_for("eventi.staff_select_event"))

        prodotti = []
        if Prodotto is not None:
            prodotti = db.query(Prodotto).filter(Prodotto.attivo == True).order_by(Prodotto.nome.asc()).all()

        if request.method == "POST":
            qr = (request.form.get("qr") or "").strip()
            cli = _cliente_by_qr(db, qr)
            if not cli:
                flash("QR non valido o cliente non trovato.", "danger")
                return redirect(url_for("consumi.staff_new"))

            # controllo ingresso -> solo warning
            if not _cliente_has_ingresso(db, cli.id_cliente, e.id_evento):
                flash("Attenzione: cliente non risulta entrato a questo evento.", "warning")

            # Prodotto/importo
            prodotto_sel_id = request.form.get("prodotto_id", type=int)
            prodotto_txt = (request.form.get("prodotto") or "").strip()
            importo_input = request.form.get("importo", type=float)
            sconto_pct = request.form.get("sconto_pct", type=float)
            punto_vendita = request.form.get("punto_vendita")
            note = (request.form.get("note") or "").strip() or None

            if punto_vendita in PUNTI and not note:
                flash("Per tavolo/privè è obbligatoria una nota (es. Tavolo 7).", "danger")
                return redirect(url_for("consumi.staff_new"))

            base_price = None
            nome_prodotto_finale = prodotto_txt
            if Prodotto is not None and prodotto_sel_id:
                p = db.query(Prodotto).get(prodotto_sel_id)
                if p:
                    base_price = float(p.prezzo)
                    nome_prodotto_finale = p.nome

            # Calcolo importo finale
            if importo_input is None:
                # se non passato, deriva da catalogo
                if base_price is None:
                    flash("Importo mancante.", "danger")
                    return redirect(url_for("consumi.staff_new"))
                importo_finale = base_price
            else:
                importo_finale = importo_input

            if sconto_pct:
                try:
                    importo_finale = round(importo_finale * (1 - float(sconto_pct)/100.0), 2)
                except Exception:
                    pass

            c = Consumo(
                cliente_id=cli.id_cliente,
                evento_id=e.id_evento,
                staff_id=_get_staff_id(),
                prodotto=nome_prodotto_finale,
                importo=importo_finale,
                punto_vendita=punto_vendita,
                note=note
            )
            db.add(c)
            db.flush()
            log_action(db, tabella="consumi", record_id=c.id_consumo, staff_id=_get_staff_id(), azione="insert")
            db.commit()
            award_on_consumo(db, cliente_id=c.cliente_id, evento_id=c.evento_id, importo_euro=c.importo)
            flash("Consumo registrato.", "success")
            return redirect(url_for("consumi.staff_new"))

        # GET
        return render_template("staff/consumi_new.html", evento=e, prodotti=prodotti)
    finally:
        db.close()

# ============================================
# 👑 ADMIN — Liste/Filtri, CRUD, Analytics
# ============================================
@consumi_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        evento_id = request.args.get("evento_id", type=int)
        staff_id = request.args.get("staff_id", type=int)
        punto = request.args.get("punto_vendita")
        qprod = (request.args.get("prodotto") or "").strip()
        dal = request.args.get("dal")
        al  = request.args.get("al")

        q = db.query(Consumo, Cliente, Evento).join(Cliente, Cliente.id_cliente == Consumo.cliente_id) \
                                              .join(Evento, Evento.id_evento == Consumo.evento_id)

        if evento_id: q = q.filter(Consumo.evento_id == evento_id)
        if staff_id:  q = q.filter(Consumo.staff_id == staff_id)
        if punto in PUNTI: q = q.filter(Consumo.punto_vendita == punto)
        if qprod: q = q.filter(Consumo.prodotto.ilike(f"%{qprod}%"))
        if dal:
            try:
                d = datetime.strptime(dal, "%Y-%m-%d")
                q = q.filter(Consumo.data_consumo >= d)
            except ValueError: pass
        if al:
            try:
                d2 = datetime.strptime(al, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(Consumo.data_consumo < d2)
            except ValueError: pass

        rows = q.order_by(Consumo.data_consumo.desc()).all()
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()
        return render_template("admin/consumi_list.html", rows=rows, eventi=eventi, staff_list=staff_list,
                               filtro={"evento_id": evento_id, "staff_id": staff_id, "punto_vendita": punto,
                                       "prodotto": qprod, "dal": dal, "al": al})
    finally:
        db.close()

@consumi_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        eventi = db.query(Evento).order_by(Evento.data_evento.desc()).all()
        clienti = db.query(Cliente).order_by(Cliente.cognome.asc(), Cliente.nome.asc()).all()
        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()
        prodotti = []
        if Prodotto is not None:
            prodotti = db.query(Prodotto).filter(Prodotto.attivo == True).order_by(Prodotto.nome.asc()).all()

        if request.method == "POST":
            cliente_id = request.form.get("cliente_id", type=int)
            evento_id  = request.form.get("evento_id", type=int)
            prodotto_sel_id = request.form.get("prodotto_id", type=int)
            prodotto_txt = (request.form.get("prodotto") or "").strip()
            importo = request.form.get("importo", type=float)
            sconto_pct = request.form.get("sconto_pct", type=float)
            punto_vendita = request.form.get("punto_vendita")
            note = (request.form.get("note") or "").strip() or None
            staff_id = request.form.get("staff_id", type=int)

            base_price = None
            nome_prodotto_finale = prodotto_txt
            if Prodotto is not None and prodotto_sel_id:
                p = db.query(Prodotto).get(prodotto_sel_id)
                if p:
                    base_price = float(p.prezzo)
                    nome_prodotto_finale = p.nome

            if importo is None:
                if base_price is None:
                    flash("Importo mancante.", "danger")
                    return redirect(url_for("consumi.admin_new"))
                importo_finale = base_price
            else:
                importo_finale = importo

            if sconto_pct:
                try:
                    importo_finale = round(importo_finale * (1 - float(sconto_pct)/100.0), 2)
                except Exception:
                    pass

            if punto_vendita in PUNTI and not note:
                flash("Per tavolo/privè è obbligatoria una nota.", "danger")
                return redirect(url_for("consumi.admin_new"))

            c = Consumo(
                cliente_id=cliente_id,
                evento_id=evento_id,
                staff_id=staff_id,
                prodotto=nome_prodotto_finale,
                importo=importo_finale,
                punto_vendita=punto_vendita,
                note=note
            )
            db.add(c)
            db.flush()
            log_action(db, tabella="consumi", record_id=c.id_consumo, staff_id=staff_id, azione="insert")
            db.commit()
            award_on_consumo(db, cliente_id=c.cliente_id, evento_id=c.evento_id, importo_euro=c.importo)
            flash("Consumo creato.", "success")
            return redirect(url_for("consumi.admin_list"))

        return render_template("admin/consumi_form.html", e=None, eventi=eventi, clienti=clienti,
                               staff_list=staff_list, prodotti=prodotti)
    finally:
        db.close()

@consumi_bp.route("/admin/<int:consumo_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(consumo_id):
    db = SessionLocal()
    try:
        c = db.query(Consumo).get(consumo_id)
        if not c:
            flash("Consumo non trovato.", "danger")
            return redirect(url_for("consumi.admin_list"))

        staff_list = db.query(Staff).order_by(Staff.nome.asc()).all()
        prodotti = []
        if Prodotto is not None:
            prodotti = db.query(Prodotto).filter(Prodotto.attivo == True).order_by(Prodotto.nome.asc()).all()

        if request.method == "POST":
            # Edit limitato: prodotto/importo/punto_vendita/note/staff
            prodotto_sel_id = request.form.get("prodotto_id", type=int)
            prodotto_txt = (request.form.get("prodotto") or "").strip()
            importo = request.form.get("importo", type=float)
            sconto_pct = request.form.get("sconto_pct", type=float)
            punto_vendita = request.form.get("punto_vendita")
            note = (request.form.get("note") or "").strip() or None
            staff_id = request.form.get("staff_id", type=int)

            nome_prodotto_finale = prodotto_txt or c.prodotto
            if Prodotto is not None and prodotto_sel_id:
                p = db.query(Prodotto).get(prodotto_sel_id)
                if p:
                    nome_prodotto_finale = p.nome
                    if importo is None:
                        importo = float(p.prezzo)

            # sconto
            if sconto_pct and importo is not None:
                try:
                    importo = round(float(importo) * (1 - float(sconto_pct)/100.0), 2)
                except Exception:
                    pass

            if punto_vendita in PUNTI and not note:
                flash("Per tavolo/privè è obbligatoria una nota.", "danger")
                return redirect(url_for("consumi.admin_edit", consumo_id=consumo_id))

            c.prodotto = nome_prodotto_finale
            if importo is not None:
                c.importo = importo
            c.punto_vendita = punto_vendita
            c.note = note
            c.staff_id = staff_id
            db.flush()
            log_action(db, tabella="consumi", record_id=c.id_consumo, staff_id=staff_id, azione="update")
            db.commit()
            flash("Consumo aggiornato.", "success")
            return redirect(url_for("consumi.admin_list"))

        return render_template("admin/consumi_form.html", e=c, eventi=[], clienti=[],
                               staff_list=staff_list, prodotti=prodotti)
    finally:
        db.close()

@consumi_bp.route("/admin/<int:consumo_id>/delete", methods=["POST"])
@require_admin
def admin_delete(consumo_id):
    db = SessionLocal()
    try:
        c = db.query(Consumo).get(consumo_id)
        if c:
            db.delete(c)
            db.flush()
            log_action(db, tabella="consumi", record_id=consumo_id, staff_id=None, azione="delete")
            db.commit()
            flash("Consumo eliminato.", "warning")
        return redirect(url_for("consumi.admin_list"))
    finally:
        db.close()

@consumi_bp.route("/admin/<int:evento_id>/analytics", methods=["GET"])
@require_admin
def admin_analytics(evento_id):
    db = SessionLocal()
    try:
        e = db.query(Evento).get(evento_id)
        if not e:
            flash("Evento non trovato.", "danger")
            return redirect(url_for("consumi.admin_list"))

        totale = db.query(func.sum(Consumo.importo)).filter(Consumo.evento_id == evento_id).scalar() or 0

        per_prodotto = dict(db.query(Consumo.prodotto, func.sum(Consumo.importo))
                              .filter(Consumo.evento_id == evento_id)
                              .group_by(Consumo.prodotto).all())

        per_punto = dict(db.query(Consumo.punto_vendita, func.sum(Consumo.importo))
                           .filter(Consumo.evento_id == evento_id)
                           .group_by(Consumo.punto_vendita).all())

        per_staff = dict(db.query(Consumo.staff_id, func.sum(Consumo.importo))
                           .filter(Consumo.evento_id == evento_id)
                           .group_by(Consumo.staff_id).all())

        # scontrino medio per cliente (evento)
        clienti_cnt = db.query(func.count(func.distinct(Consumo.cliente_id))) \
                        .filter(Consumo.evento_id == evento_id).scalar() or 0
        scontrino_medio = round(totale / clienti_cnt, 2) if clienti_cnt else 0

        # top spender (evento) — top 10
        top_spender = db.query(Cliente, func.sum(Consumo.importo).label("spesa")) \
                        .join(Cliente, Cliente.id_cliente == Consumo.cliente_id) \
                        .filter(Consumo.evento_id == evento_id) \
                        .group_by(Cliente.id_cliente) \
                        .order_by(func.sum(Consumo.importo).desc()) \
                        .limit(10).all()

        return render_template("admin/consumi_analytics.html", e=e, totale=totale, per_prodotto=per_prodotto,
                               per_punto=per_punto, per_staff=per_staff,
                               scontrino_medio=scontrino_medio, top_spender=top_spender)
    finally:
        db.close()