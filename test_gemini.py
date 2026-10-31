import os
from dotenv import load_dotenv
from google import genai

# 1. Lire la clé et le modèle dans le fichier .env
load_dotenv()
cle = os.getenv("GEMINI_API_KEY")
modele = os.getenv("GEMINI_MODEL")

# 2. Se connecter à Gemini
client = genai.Client(api_key=cle)

# 3. Poser une question
reponse = client.models.generate_content(
    model=modele,
    contents="Donne en une phrase la définition métier d'un numéro de lot dans l'industrie pharmaceutique.",
)

# 4. Afficher la réponse
print("Modèle utilisé :", modele)
print(reponse.text)
