"""Boîte à outils commune aux deux standards (plomberie technique, aucune règle métier).

Avant toute chose, un agent ou un lanceur indique pour quel standard il travaille :
    utiliser_standard("groupe")   ou   utiliser_standard("bis")
Tous les chemins (charte, registre, base, données, rapports) en sont déduits.
"""
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import errors

# Racine du projet = le dossier qui contient "commun"
RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")

STANDARDS = ("groupe", "bis")
STANDARD = None   # standard actif : "groupe" ou "bis"
DOSSIER = None    # ex. .../standard_groupe
BASE = None       # ex. .../standard_groupe/catalogue.db
REGLES = None     # ex. .../standard_groupe/config/regles.json
REGISTRE = None   # ex. .../standard_groupe/config/registre.xlsx
_client = None


def utiliser_standard(standard):
    """Choisit le standard actif et en déduit tous les chemins."""
    global STANDARD, DOSSIER, BASE, REGLES, REGISTRE
    if standard not in STANDARDS:
        raise ValueError(f"Standard inconnu : {standard!r}. Valeurs possibles : groupe ou bis.")
    STANDARD = standard
    DOSSIER = RACINE / f"standard_{standard}"
    BASE = DOSSIER / "catalogue.db"
    REGLES = DOSSIER / "config" / "regles.json"
    REGISTRE = DOSSIER / "config" / "registre.xlsx"


def _verifier_standard():
    if STANDARD is None:
        raise RuntimeError('Aucun standard choisi : appelez d\'abord utiliser_standard("groupe") ou utiliser_standard("bis").')


def chemin(*morceaux):
    """Chemin dans le dossier du standard actif. Exemple : chemin("rapports", "bilan.txt")"""
    _verifier_standard()
    return DOSSIER.joinpath(*morceaux)


def charger_regles():
    """Lit la charte du standard actif."""
    _verifier_standard()
    with open(REGLES, encoding="utf-8") as f:
        return json.load(f)


def infos_domaine(domaine):
    """Renvoie les acteurs d'un domaine, lus dans le registre du standard actif."""
    _verifier_standard()
    registre = pd.read_excel(REGISTRE, dtype=str).fillna("")
    lignes = registre[registre["domaine"] == domaine]
    if lignes.empty:
        raise ValueError(f"Le domaine {domaine!r} n'est pas dans le registre du standard {STANDARD}.")
    return lignes.iloc[0].to_dict()


def demander_gemini(consigne, essais=3):
    """Envoie une consigne à Gemini et renvoie sa réponse JSON.
    Gère la surcharge (503), le quota (429) et les réponses JSON mal formées ;
    en dernier recours, utilise le modèle de secours."""
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
                resultat = json.loads(reponse.text)
                # Si Gemini emballe la liste dans un objet {"fiches": [...]}, on récupère la liste
                if isinstance(resultat, dict) and len(resultat) == 1 and isinstance(next(iter(resultat.values())), list):
                    resultat = next(iter(resultat.values()))
                print(f"  (réponse fournie par {modele})")
                return resultat
            except json.JSONDecodeError:
                print(f"  Réponse JSON mal formée de {modele} (essai {essai}/{essais}) : nouvelle demande…")
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


def connexion(creer=False):
    """Ouvre la base du standard actif.
    creer=True seulement pour la créer (creer_base.py) ; sinon, une base absente est une erreur."""
    _verifier_standard()
    if not creer and not BASE.exists():
        raise FileNotFoundError(f"La base {BASE} n'existe pas encore : lancez d'abord le lanceur du standard {STANDARD}.")
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
    """Modifie une fiche et trace l'action dans l'historique (ignore un id inconnu)."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    con = connexion()
    ligne = con.execute("SELECT statut FROM fiches WHERE id = ?", (fiche_id,)).fetchone()
    if ligne is None:
        con.close()
        return
    ancien_statut = ligne["statut"]
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


# Petit test : python commun\outils.py groupe   (ajoutez --gemini pour tester aussi l'appel à Gemini)
if __name__ == "__main__":
    standard = sys.argv[1] if len(sys.argv) > 1 else "groupe"
    utiliser_standard(standard)
    print(f"Standard actif : {STANDARD}")
    for nom, p in [("Charte", REGLES), ("Registre", REGISTRE), ("Base", BASE)]:
        print(f"  {'✅' if p.exists() else '❌'} {nom} : {p.relative_to(RACINE)}")
    print("  Version de la charte :", charger_regles()["version"])
    print("  Domaines du registre :", pd.read_excel(REGISTRE, dtype=str)["domaine"].tolist())
    if BASE.exists():
        print("  Fiches au statut Identifié :", len(lire_fiches(statut="Identifié")))
    else:
        print("  (base pas encore créée : normal à ce stade, elle le sera à l'étape M7)")
    if "--gemini" in sys.argv:
        print("  Test Gemini :", demander_gemini('Réponds uniquement en JSON avec la forme {"etat": "ok", "phrase": "..."} où phrase est une phrase de 6 mots sur la gouvernance des données.'))