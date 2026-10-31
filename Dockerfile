# On utilise une version allégée de Linux avec Python 3.11
FROM python:3.11-slim

# On crée le dossier de travail dans le conteneur
WORKDIR /app

# On copie uniquement la liste des dépendances en premier (optimisation)
COPY requirements.txt .

# On installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# On copie le reste de ton code (main.py, HTML, etc.)
COPY . .

# On signale que l'application écoute sur le port 8000
EXPOSE 8000

# La commande de démarrage exacte pour Uvicorn dans le cloud
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]