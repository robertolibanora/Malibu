#!/bin/bash
# Script per attendere che MySQL sia pronto prima di avviare l'applicazione

set -e

host="$1"
port="${2:-3306}"
shift 2
cmd="$@"

# Usa la variabile d'ambiente passata dal docker-compose
root_password="${MYSQL_ROOT_PASSWORD:-rootpassword}"

echo "⏳ Attendo che MySQL sia pronto su $host:$port..."

# Attendi fino a 60 secondi che MySQL sia pronto
max_attempts=30
attempt=0

until mysqladmin ping -h "$host" -P "$port" -u root -p"$root_password" --silent 2>/dev/null; do
  attempt=$((attempt + 1))
  if [ $attempt -ge $max_attempts ]; then
    >&2 echo "❌ Timeout: MySQL non è diventato disponibile dopo $max_attempts tentativi"
    exit 1
  fi
  >&2 echo "MySQL non è ancora pronto - aspetto... (tentativo $attempt/$max_attempts)"
  sleep 2
done

>&2 echo "✅ MySQL è pronto!"
exec $cmd

