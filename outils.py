import json
import os
import sqlite3
import time
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()
BASE = "catalogue.db"
_client = None


def charger_regles():
    """Lit le fichier de règles du Data Governance Leader."""
    with open("config/regles.json", encoding="utf-8") as f:
        return json.load(f)


def infos_domaine(domaine):
    """Renvoie le standard (groupe ou bis) et les acteurs d'un domaine."""
    regles = charger_regles()
    registre = pd.read_excel(regles["registre_domaines"], dtype=str).fillna("")
    return registre[registre["domaine"] == domaine].iloc[0].to_dict()


def demander_gemini(consigne, essais=3):
    """Envoie une consigne à Gemini et renvoie sa réponse (JSON) sous forme de dictionnaire.
    Si le modèle est surchargé, attend puis réessaie ; en dernier recours, utilise le modèle de secours."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    modeles = [os.getenv("GEMINI_MODEL")]
    if os.getenv("GEMINI_MODEL_SECOURS"):
        modeles.append(os.getenv("GEMINI_MODEL_SECOURS"))

    for modele in modeles:
        for essai in range(1, essais + 1):
            try:
                reponse = _client.models.generate_content(
                    model=modele,
                    contents=consigne,
                    config={"response_mime_type": "application/json"},
                )
                print(f"  (réponse fournie par {modele})")
                return json.loads(reponse.text)
            except errors.ServerError:
                print(f"  {modele} surchargé (essai {essai}/{essais}) : nouvelle tentative dans 30 s…")
                time.sleep(30)
            except errors.ClientError as e:
                if e.code == 429:
                    print(f"  Quota gratuit atteint sur {modele} (essai {essai}/{essais}) : nouvelle tentative dans 60 s…")
                    time.sleep(60)
                else:
                    raise
    raise RuntimeError("Gemini est indisponible pour le moment : réessayez plus tard.")


def connexion():
    con = sqlite3.connect(BASE)
    con.row_factory = sqlite3.Row
    return con


def lire_fiches(**filtres):
    """Lit les fiches du catalogue. Exemple : lire_fiches(statut="Identifié", domaine="Finance")"""
    con = connexion()
    requete = "SELECT * FROM fiches"
    if filtres:
        requete += " WHERE " + " AND ".join(f"{cle} = ?" for cle in filtres)
    fiches = [dict(ligne) for ligne in con.execute(requete, tuple(filtres.values()))]
    con.close()
    return fiches


def mettre_a_jour(fiche_id, auteur, action, champs, detail=""):
    """Modifie une fiche et trace l'action dans l'historique."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    con = connexion()
    ancien_statut = con.execute("SELECT statut FROM fiches WHERE id = ?", (fiche_id,)).fetchone()["statut"]
    champs = dict(champs)
    champs["maj_le"] = maintenant
    affectations = ", ".join(f"{cle} = ?" for cle in champs)
    con.execute(f"UPDATE fiches SET {affectations} WHERE id = ?", (*champs.values(), fiche_id))
    con.execute(
        "INSERT INTO historique (fiche_id, date, auteur, action, ancien_statut, nouveau_statut, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fiche_id, maintenant, auteur, action, ancien_statut, champs.get("statut", ancien_statut), detail),
    )
    con.commit()
    con.close()


# Petit test quand on lance ce fichier directement
if __name__ == "__main__":
    print("Règles version :", charger_regles()["version"])
    print("Finance :", infos_domaine("Finance")["standard"])
    print("Supply Chain :", infos_domaine("Supply Chain")["standard"])
    print("Fiches au statut Identifié :", len(lire_fiches(statut="Identifié")))
    test = demander_gemini('Réponds uniquement en JSON avec la forme {"etat": "ok", "phrase": "..."} où phrase est une phrase de 6 mots sur la gouvernance des données.')
    print("Test Gemini (JSON) :", test)