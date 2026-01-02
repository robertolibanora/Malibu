# Dockerfile multi-stage per applicazione Flask Malibu
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Installa dipendenze di sistema necessarie per build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

WORKDIR /app

# Installa solo runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia dipendenze Python dallo stage builder
COPY --from=builder /root/.local /root/.local

# Assicura che le librerie siano nel PATH
ENV PATH=/root/.local/bin:$PATH

# Copia il codice sorgente
COPY . .

# Crea directory per uploads se non esiste
RUN mkdir -p static/uploads/eventi

# Copia e rendi eseguibili gli script di utilità
COPY docker/wait-for-db.sh /usr/local/bin/wait-for-db.sh
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/wait-for-db.sh /usr/local/bin/entrypoint.sh

# Installa mysql-client per wait-for-db.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Esponi la porta dell'applicazione
EXPOSE 8123

# Variabili d'ambiente di default (possono essere sovrascritte)
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1

# Usa entrypoint script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Comando di avvio
CMD ["python", "run.py"]

