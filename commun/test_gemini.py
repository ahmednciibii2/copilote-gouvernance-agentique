"""Test de connexion à Gemini (un seul appel) : vérifie la clé et les modèles déclarés dans .env.

Usage, depuis la racine du projet :
    python -m commun.test_gemini
"""
import os

from commun.outils import demander_gemini

print("Modèle principal :", os.getenv("GEMINI_MODEL"))
print("Modèle de secours :", os.getenv("GEMINI_MODEL_SECOURS") or "(aucun)")
print("Clé présente :", "oui" if os.getenv("GEMINI_API_KEY") else "NON — vérifier le fichier .env")

reponse = demander_gemini(
    'Réponds uniquement en JSON avec la forme {"definition": "..."} : '
    "donne en une phrase la définition métier d'un numéro de lot dans une entreprise industrielle."
)
print("Réponse :", reponse)
