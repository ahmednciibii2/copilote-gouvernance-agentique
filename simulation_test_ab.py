from agents.croisement_a_vers_b import rattacher_colonnes
from outils import lire_fiches

for domaine in ["Finance", "Supply Chain"]:
    rattacher_colonnes(domaine)

noms = {t["id"]: t["nom"] for t in lire_fiches(chemin="B")}
print("\n--- Croisement A → B ---")
for c in lire_fiches(chemin="A"):
    terme = c["terme_lie"]
    lisible = noms.get(terme, terme)
    print(f'{c["nom"]} → {lisible} | critique={c["critique"]} | suivant={c["acteur_suivant"]}')