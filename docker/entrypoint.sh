#!/bin/bash
# Entrypoint script per il container Flask

set -e

echo "🚀 Avvio applicazione Malibu..."

# Crea directory uploads se non esiste
mkdir -p /app/static/uploads/eventi

# Imposta permessi corretti per uploads
chmod -R 755 /app/static/uploads/ 2>/dev/null || true

# Se il file .env non esiste, crea uno di default
if [ ! -f /app/.env ]; then
    echo "⚠️  File .env non trovato, creo uno di default..."
    cat > /app/.env << EOF
# Database Configuration
DB_USER=malibu_user
DB_PASSWORD=malibu_password
DB_HOST=db
DB_NAME=malibu
DB_PORT=3306
USE_SQLITE=false

# Flask Configuration
SECRET_KEY=dev-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=1
EOF
fi

# Esegue il comando passato (di default: python run.py)
exec "$@"

