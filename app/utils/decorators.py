#!/usr/bin/env python3
"""
Decoratori di autenticazione centralizzati per il progetto Malibù.

Questi decoratori possono essere usati su tutte le route che richiedono
autenticazione specifica per clienti o amministratori.

Esempi d'uso:

    from app.utils.decorators import require_cliente, require_admin

    @app.route("/protected-cliente")
    @require_cliente
    def client_page():
        return "Solo per clienti loggati"

    @app.route("/admin-panel")
    @require_admin
    def admin_page():
        return "Solo per amministratori"
"""
from flask import session, abort, redirect, url_for, flash
from functools import wraps


def require_cliente(f):
    """
    Decoratore che richiede un cliente loggato.

    Aborta con 401 se nessun cliente_id in sessione.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("cliente_id"):
            abort(401)
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """
    Decoratore che richiede un amministratore loggato.

    Aborta con 403 se staff_role != 'admin'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("staff_role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def require_staff(f):
    """
    Decoratore che richiede un membro dello staff loggato.
    
    Reindirizza al login se nessuno staff_id in sessione.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("staff_id"):
            flash("Devi effettuare l'accesso staff.", "error")
            return redirect(url_for("auth.auth_login_form"))  # usiamo il login shared
        return f(*args, **kwargs)
    return wrapper
