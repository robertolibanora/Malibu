# app/routes/prodotti.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import SessionLocal
from app.models.prodotti import Prodotto
from app.utils.decorators import require_admin

prodotti_bp = Blueprint("prodotti", __name__, url_prefix="/prodotti")

# ============================================
# 👑 ADMIN — Gestione Listino
# ============================================
@prodotti_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    """Lista prodotti del listino"""
    db = SessionLocal()
    try:
        categoria = request.args.get("categoria", "").strip()
        attivo = request.args.get("attivo")
        
        q = db.query(Prodotto)
        
        if categoria:
            q = q.filter(Prodotto.categoria.ilike(f"%{categoria}%"))
        if attivo == "si":
            q = q.filter(Prodotto.attivo == True)
        elif attivo == "no":
            q = q.filter(Prodotto.attivo == False)
        
        prodotti = q.order_by(Prodotto.categoria.asc(), Prodotto.nome.asc()).all()
        
        # Categorie disponibili
        categorie = db.query(Prodotto.categoria).distinct().filter(Prodotto.categoria.isnot(None)).all()
        categorie = [c[0] for c in categorie]
        
        return render_template("admin/prodotti_list.html",
                             prodotti=prodotti,
                             categorie=categorie,
                             filtro={"categoria": categoria, "attivo": attivo})
    finally:
        db.close()


@prodotti_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    """Crea nuovo prodotto"""
    db = SessionLocal()
    try:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            prezzo = request.form.get("prezzo", type=float)
            categoria = request.form.get("categoria", "").strip() or None
            
            if not nome or prezzo is None:
                flash("Nome e prezzo sono obbligatori.", "danger")
                return redirect(url_for("prodotti.admin_new"))
            
            if prezzo < 0:
                flash("Il prezzo non può essere negativo.", "danger")
                return redirect(url_for("prodotti.admin_new"))
            
            p = Prodotto(
                nome=nome,
                prezzo=prezzo,
                categoria=categoria,
                attivo=True
            )
            db.add(p)
            db.commit()
            flash("Prodotto creato.", "success")
            return redirect(url_for("prodotti.admin_list"))
        
        # GET - carica categorie esistenti per suggerimenti
        categorie = db.query(Prodotto.categoria).distinct().filter(Prodotto.categoria.isnot(None)).all()
        categorie = [c[0] for c in categorie]
        
        return render_template("admin/prodotti_form.html", prodotto=None, categorie=categorie)
    finally:
        db.close()


@prodotti_bp.route("/admin/<int:prodotto_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(prodotto_id):
    """Modifica prodotto"""
    db = SessionLocal()
    try:
        p = db.query(Prodotto).get(prodotto_id)
        if not p:
            flash("Prodotto non trovato.", "danger")
            return redirect(url_for("prodotti.admin_list"))
        
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            prezzo = request.form.get("prezzo", type=float)
            categoria = request.form.get("categoria", "").strip() or None
            
            if not nome or prezzo is None:
                flash("Nome e prezzo sono obbligatori.", "danger")
                return redirect(url_for("prodotti.admin_edit", prodotto_id=prodotto_id))
            
            if prezzo < 0:
                flash("Il prezzo non può essere negativo.", "danger")
                return redirect(url_for("prodotti.admin_edit", prodotto_id=prodotto_id))
            
            p.nome = nome
            p.prezzo = prezzo
            p.categoria = categoria
            p.attivo = True
            db.commit()
            flash("Prodotto aggiornato.", "success")
            return redirect(url_for("prodotti.admin_list"))
        
        # GET
        categorie = db.query(Prodotto.categoria).distinct().filter(Prodotto.categoria.isnot(None)).all()
        categorie = [c[0] for c in categorie]
        
        return render_template("admin/prodotti_form.html", prodotto=p, categorie=categorie)
    finally:
        db.close()


@prodotti_bp.route("/admin/<int:prodotto_id>/delete", methods=["POST"])
@require_admin
def admin_delete(prodotto_id):
    """Elimina prodotto"""
    db = SessionLocal()
    try:
        p = db.query(Prodotto).get(prodotto_id)
        if p:
            db.delete(p)
            db.commit()
            flash("Prodotto eliminato.", "warning")
        return redirect(url_for("prodotti.admin_list"))
    finally:
        db.close()

