from app.routes.clienti import clienti_bp, dashboard_bp
from app.routes.auth import auth_bp
from app.routes.eventi import eventi_bp
from app.routes.prenotazioni import prenotazioni_bp
from app.routes.ingressi import ingressi_bp
from app.routes.consumi import consumi_bp
from app.routes.fedelta import fedelta_bp
from app.routes.feedback import feedback_bp
from app.routes.staff import staff_bp, staff_admin_bp
from app.routes.log_attivita import log_bp
from app.routes.prodotti import prodotti_bp
from app.routes.stats import stats_bp

# Esportiamo tutti i blueprint in una lista centralizzata
# Nota: staff_bp e staff_admin_bp sono registrati manualmente in app/__init__.py
all_blueprints = [
    clienti_bp,
    dashboard_bp,
    auth_bp,
    eventi_bp,
    prenotazioni_bp,
    ingressi_bp,
    consumi_bp,
    fedelta_bp,
    feedback_bp,
    log_bp,
    prodotti_bp,
    stats_bp,
]