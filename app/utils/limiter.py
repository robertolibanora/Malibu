"""
Rate Limiter centralizzato per MalibuApp.

Questo modulo esporta il limiter che viene inizializzato in app/__init__.py
e può essere usato nei blueprint per applicare rate limiting.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Limiter globale - viene inizializzato in app/__init__.py
# Inizializzato con app=None per supporto lazy (associato dopo)
limiter = Limiter(
    app=None,
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",  # Per produzione, considerare Redis
    strategy="fixed-window"
)

def init_limiter(app):
    """Inizializza il limiter con l'app Flask"""
    global limiter
    limiter.app = app
    return limiter

