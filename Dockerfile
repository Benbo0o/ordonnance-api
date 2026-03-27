FROM python:3.12-slim

# LibreOffice pour la conversion PDF
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    fonts-liberation \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /api

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

# Répertoire pour les PDFs temporaires
RUN mkdir -p /tmp/ordonnances

# Variables d'environnement
ENV PYTHONPATH=/api
ENV ANTHROPIC_API_KEY=""

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
