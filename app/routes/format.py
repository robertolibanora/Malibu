# app/routes/format.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import SessionLocal
from app.utils.decorators import require_admin
from app.models.template_eventi import TemplateEvento

format_bp = Blueprint("format", __name__, url_prefix="/format")


@format_bp.route("/admin", methods=["GET"])
@require_admin
def admin_list():
    db = SessionLocal()
    try:
        formats = db.query(TemplateEvento).order_by(TemplateEvento.nome.asc()).all()
        return render_template("admin/format_list.html", formats=formats)
    finally:
        db.close()


@format_bp.route("/admin/new", methods=["GET", "POST"])
@require_admin
def admin_new():
    db = SessionLocal()
    try:
        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            categoria = request.form.get("categoria") or "altro"
            tipo_musica = (request.form.get("tipo_musica") or "").strip() or None
            capienza = request.form.get("capienza", type=int)
            if not nome:
                flash("Nome obbligatorio.", "danger")
                return redirect(url_for("format.admin_new"))
            t = TemplateEvento(nome=nome, categoria=categoria, tipo_musica=tipo_musica, capienza=capienza)
            db.add(t)
            db.commit()
            flash("Format creato.", "success")
            return redirect(url_for("format.admin_list"))
        return render_template("admin/format_form.html", e=None)
    finally:
        db.close()


@format_bp.route("/admin/<int:template_id>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit(template_id: int):
    db = SessionLocal()
    try:
        t = db.query(TemplateEvento).get(template_id)
        if not t:
            flash("Format non trovato.", "danger")
            return redirect(url_for("format.admin_list"))
        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            categoria = request.form.get("categoria") or "altro"
            tipo_musica = (request.form.get("tipo_musica") or "").strip() or None
            capienza = request.form.get("capienza", type=int)
            if not nome:
                flash("Nome obbligatorio.", "danger")
                return redirect(url_for("format.admin_edit", template_id=template_id))
            t.nome = nome
            t.categoria = categoria
            t.tipo_musica = tipo_musica
            t.capienza = capienza
            db.commit()
            flash("Format aggiornato.", "success")
            return redirect(url_for("format.admin_list"))
        return render_template("admin/format_form.html", e=t)
    finally:
        db.close()


@format_bp.route("/admin/<int:template_id>/delete", methods=["POST"])
@require_admin
def admin_delete(template_id: int):
    db = SessionLocal()
    try:
        t = db.query(TemplateEvento).get(template_id)
        if t:
            db.delete(t)
            db.commit()
            flash("Format eliminato.", "warning")
        return redirect(url_for("format.admin_list"))
    finally:
        db.close()
