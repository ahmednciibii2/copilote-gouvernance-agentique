from agents.agent_bis_leader import confirmer
from agents.agent_bis_manager import traiter_business_object
from outils import lire_fiches

OBJETS = [("Finance", "Fournisseur"), ("Supply Chain", "Lot de production")]

for domaine, objet in OBJETS:
    traiter_business_object(domaine, objet)
for domaine in ["Finance", "Supply Chain"]:
    confirmer(domaine)

print("\n--- État du catalogue (standard bis) ---")
for domaine, objet in OBJETS:
    for f in lire_fiches(domaine=domaine, business_object=objet):
        print(f'{f["nom"]} | critique={f["critique"]} | statut={f["statut"]} | suivant={f["acteur_suivant"]} | rejets={f["nb_rejets"]}')
        if f["motif_rejet"]:
            print("    Motif :", f["motif_rejet"])