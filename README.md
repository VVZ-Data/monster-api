# Monster API Collection 🟢
Une API REST (FastAPI) couplée à une base PostgreSQL pour gérer ma collection de canettes Monster.

## Pour lancer le projet en local :
1. Créer un environnement virtuel : `python -m venv venv`
2. Installer les dépendances : `pip install -r requirements.txt`
3. Créer un fichier `.env` avec la variable `DATABASE_URL="postgresql://..."`
4. Lancer le serveur : `uvicorn main:app --reload`