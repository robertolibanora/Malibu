# app/routes/promozioni.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from app.database import SessionLocal
from app.models.promozioni import Promozione, ClientePromozione
from app.models.clienti import Cliente
from app.utils.decorators import require_admin

promozioni_bp = Blueprint("promozioni", __name__, url_prefix="/promozioni")

@promozioni_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    """Vista legacy: le promozioni evento sono ora testo libero nella creazione evento.

    Manteniamo la route solo per evitare 404 su eventuali link vecchi.
    """
    flash("La gestione promozioni è stata semplificata: usa il campo 'Promozione' nella scheda evento.", "info")
    return redirect(url_for("eventi.admin_list"))

@promozioni_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    flash("La creazione di promozioni dedicate non è più disponibile. Inserisci la promo direttamente nel campo 'Promozione' dell'evento.", "info")
    return redirect(url_for("eventi.admin_list"))

@promozioni_bp.route("/admin/<int:promozione_id>", methods=["GET"])
@require_admin
def admin_promozione_detail(promozione_id):
    db = SessionLocal()
    try:
        from sqlalchemy import func
        p = db.query(Promozione).get(promozione_id)
        if not p:
            flash("Promozione non trovata.", "danger")
            return redirect(url_for("promozioni.admin_list"))
        
        # Statistiche
        tot_assegnate = db.query(func.count(ClientePromozione.id)).filter(
            ClientePromozione.promozione_id == promozione_id
        ).scalar() or 0
        
        tot_usate = db.query(func.count(ClientePromozione.id)).filter(
            ClientePromozione.promozione_id == promozione_id,
            ClientePromozione.usata == True
        ).scalar() or 0
        
        tot_attive = db.query(func.count(ClientePromozione.id)).filter(
            ClientePromozione.promozione_id == promozione_id,
            ClientePromozione.usata == False,
            (ClientePromozione.data_scadenza.is_(None)) | (ClientePromozione.data_scadenza >= date.today())
        ).scalar() or 0
        
        # Ultime assegnazioni
        ultime_assegnazioni = db.query(ClientePromozione, Cliente)\
                                .join(Cliente, Cliente.id_cliente == ClientePromozione.cliente_id)\
                                .filter(ClientePromozione.promozione_id == promozione_id)\
                                .order_by(ClientePromozione.data_assegnazione.desc())\
                                .limit(20).all()
        
        return render_template("admin/promozione_detail.html",
                             promozione=p,
                             tot_assegnate=tot_assegnate,
                             tot_usate=tot_usate,
                             tot_attive=tot_attive,
                             ultime_assegnazioni=ultime_assegnazioni,
                             oggi=date.today())
    finally:
        db.close()

@promozioni_bp.route("/admin/<int:promozione_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(promozione_id):
    db = SessionLocal()
    try:
        p = db.query(Promozione).get(promozione_id)
        if not p:
            flash("Promozione non trovata.", "danger")
            return redirect(url_for("promozioni.admin_list"))
        
        if request.method == "POST":
            p.nome = request.form.get("nome", "").strip()
            p.descrizione = request.form.get("descrizione", "").strip() or None
            p.tipo = request.form.get("tipo", "altro")
            p.valore = request.form.get("valore", type=float) or None
            p.condizioni = request.form.get("condizioni", "").strip() or None
            p.attiva = request.form.get("attiva") == "on"
            p.data_inizio = request.form.get("data_inizio") or None
            p.data_fine = request.form.get("data_fine") or None
            p.livello_richiesto = request.form.get("livello_richiesto") or None
            p.punti_richiesti = request.form.get("punti_richiesti", type=int) or None
            p.auto_assegnazione = request.form.get("auto_assegnazione") == "on"
            db.commit()
            flash("Promozione aggiornata.", "success")
            return redirect(url_for("promozioni.admin_promozione_detail", promozione_id=promozione_id))
        
        return render_template("admin/promozioni_form.html", p=p)
    finally:
        db.close()

@promozioni_bp.route("/admin/<int:promozione_id>/delete", methods=["POST"])
@require_admin
def admin_delete(promozione_id):
    db = SessionLocal()
    try:
        p = db.query(Promozione).get(promozione_id)
        if p:
            db.delete(p)
            db.commit()
            flash("Promozione eliminata.", "warning")
        return redirect(url_for("promozioni.admin_list"))
    finally:
        db.close()

@promozioni_bp.route("/admin/<int:promozione_id>/assign/<int:cliente_id>", methods=["POST"])
@require_admin
def admin_assign(cliente_id, promozione_id):
    db = SessionLocal()
    try:
        # Se promozione_id è 0, prendilo dal form
        if promozione_id == 0:
            promozione_id = request.form.get("promozione_id", type=int)
            if not promozione_id:
                flash("Seleziona una promozione.", "danger")
                return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
        
        # Verifica se già assegnata
        existing = db.query(ClientePromozione).filter(
            ClientePromozione.cliente_id == cliente_id,
            ClientePromozione.promozione_id == promozione_id
        ).first()
        
        if existing:
            flash("Promozione già assegnata a questo cliente.", "warning")
            return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
        
        p = db.query(Promozione).get(promozione_id)
        if not p:
            flash("Promozione non trovata.", "danger")
            return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
        
        cp = ClientePromozione(
            cliente_id=cliente_id,
            promozione_id=promozione_id,
            data_scadenza=p.data_fine
        )
        db.add(cp)
        db.commit()
        flash("Promozione assegnata.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

@promozioni_bp.route("/admin/<int:promozione_id>/unassign/<int:cliente_id>", methods=["POST"])
@require_admin
def admin_unassign(cliente_id, promozione_id):
    db = SessionLocal()
    try:
        cp = db.query(ClientePromozione).filter(
            ClientePromozione.cliente_id == cliente_id,
            ClientePromozione.promozione_id == promozione_id
        ).first()
        if cp:
            db.delete(cp)
            db.commit()
            flash("Promozione rimossa.", "success")
        return redirect(url_for("clienti.admin_cliente_detail", cliente_id=cliente_id))
    finally:
        db.close()

