FROM python:3.9-slim

WORKDIR /app

# Copier requirements.txt en premier pour utiliser le cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Port par défaut (sera overridé par $PORT si défini)
ENV PORT=3000

EXPOSE $PORT

# Démarrer l'application
CMD uvicorn main:app --host 0.0.0.0 --port $PORT

