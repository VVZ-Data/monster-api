from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import psycopg2
import os
import re
from dotenv import load_dotenv

# 1. On charge le mot de passe depuis ton fichier .env
load_dotenv()

app = FastAPI()

def verifier_mot_de_passe(x_api_key: str = Header(...)):
    mot_de_passe_attendu = os.getenv("ADMIN_PASSWORD")
    if x_api_key != mot_de_passe_attendu:
        raise HTTPException(status_code=403, detail="Accès refusé : mauvais mot de passe")

# 2. On autorise ton futur frontend web à communiquer avec l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Le Bouclier Pydantic : vérifie les données avant insertion
class CanetteForm(BaseModel):
    nom: str
    gamme: str
    pays_origine: Optional[str] = None
    etat: str = Field(..., pattern="^(Parfait état|Abîmée|Très abîmée)$")
    date_ajout: str

    @field_validator("date_ajout")
    @classmethod
    def valider_et_formater_date(cls, valeur_saisie: str) -> str:
        if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", valeur_saisie):
            return f"{valeur_saisie}-01"
        elif re.match(r"^(0[1-9]|1[0-2])-\d{4}$", valeur_saisie):
            mois, annee = valeur_saisie.split("-")
            return f"{annee}-{mois}-01"
        raise ValueError("La date doit être au format YYYY-MM ou MM-YYYY")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# 4. La Route POST : insérer une canette
@app.post("/api/canettes/", dependencies=[Depends(verifier_mot_de_passe)])
def ajouter_canette(canette: CanetteForm):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        requete_sql = """
            INSERT INTO collection_monster (nom, gamme, pays_origine, etat, date_ajout)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, TO_CHAR(date_ajout, 'YYYY-MM');
        """
        valeurs = (canette.nom, canette.gamme, canette.pays_origine, canette.etat, canette.date_ajout)
        cursor.execute(requete_sql, valeurs)
        resultat = cursor.fetchone()
        conn.commit()
        return {
            "message": f"{canette.nom} ajoutée avec succès !",
            "id_canette": resultat[0],
            "date_enregistree": resultat[1]
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/filtres/gammes")
def lister_gammes_existantes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT gamme FROM collection_monster WHERE gamme IS NOT NULL;")
    gammes = [ligne[0] for ligne in cursor.fetchall()]
    conn.close()
    return gammes

@app.get("/api/filtres/pays")
def lister_pays_existants():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT pays_origine FROM collection_monster WHERE pays_origine IS NOT NULL;")
    pays = [ligne[0] for ligne in cursor.fetchall()]
    conn.close()
    return pays

@app.get("/api/canettes/recherche")
def rechercher_canettes(
    nom: Optional[str] = None,
    gamme: Optional[str] = None,
    pays: Optional[str] = None,
    periode: Optional[str] = Query(None, description="ce_mois, cette_annee, 1_an, 2_ans")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    requete = "SELECT id, nom, gamme, pays_origine, etat, TO_CHAR(date_ajout, 'YYYY-MM') FROM collection_monster WHERE 1=1"
    valeurs = []
    
    if nom:
        requete += " AND nom %% %s" # On a doublé le %
        valeurs.append(nom)
    if gamme:
        requete += " AND gamme = %s"
        valeurs.append(gamme)
    if pays:
        requete += " AND pays_origine = %s"
        valeurs.append(pays)
        
    if periode == "ce_mois":
        requete += " AND DATE_TRUNC('month', date_ajout) = DATE_TRUNC('month', CURRENT_DATE)"
    elif periode == "cette_annee":
        requete += " AND EXTRACT(YEAR FROM date_ajout) = EXTRACT(YEAR FROM CURRENT_DATE)"
    elif periode == "1_an":
        requete += " AND EXTRACT(YEAR FROM date_ajout) = EXTRACT(YEAR FROM CURRENT_DATE) - 1"
    elif periode == "2_ans":
        requete += " AND EXTRACT(YEAR FROM date_ajout) = EXTRACT(YEAR FROM CURRENT_DATE) - 2"
        
    if nom:
        requete += " ORDER BY similarity(nom, %s) DESC"
        valeurs.append(nom)
    else:
        requete += " ORDER BY date_ajout DESC"
        
    try:
        cursor.execute(requete, tuple(valeurs))
        resultats = cursor.fetchall()
        canettes = []
        for row in resultats:
            canettes.append({
                "id": row[0], "nom": row[1], "gamme": row[2],
                "pays_origine": row[3], "etat": row[4], "date_ajout": row[5]
            })
        return canettes
    finally:
        cursor.close()
        conn.close()

@app.put("/api/canettes/{id_canette}", dependencies=[Depends(verifier_mot_de_passe)])
def modifier_canette(id_canette: int, canette: CanetteForm):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        requete_sql = """
            UPDATE collection_monster 
            SET nom = %s, gamme = %s, pays_origine = %s, etat = %s, date_ajout = %s
            WHERE id = %s
            RETURNING id;
        """
        # canette.date_ajout contient la date formatée grâce au validateur Pydantic
        valeurs = (canette.nom, canette.gamme, canette.pays_origine, canette.etat, canette.date_ajout, id_canette)
        
        cursor.execute(requete_sql, valeurs)
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Canette introuvable")
            
        conn.commit()
        return {"message": "Canette mise à jour avec succès"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.delete("/api/canettes/{id_canette}", dependencies=[Depends(verifier_mot_de_passe)])
def supprimer_canette(id_canette: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM collection_monster WHERE id = %s RETURNING id;", (id_canette,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Canette introuvable")
            
        conn.commit()
        return {"message": "Canette supprimée de la collection"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()