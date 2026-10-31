from agents.agent_grp_leader import controler
from agents.agent_grp_owner import preparer_decision
from agents.agent_grp_steward import documenter_business_object
from outils import lire_fiches

DOMAINE, OBJET = "Supply Chain", "Lot de production"

documenter_business_object(DOMAINE, OBJET)  # reprend les fiches « À corriger »
controler(DOMAINE)                          # recontrôle des fiches corrigées
preparer_decision(DOMAINE)                  # dossiers de décision pour l'Owner humain

print("\n--- État du catalogue ---")
for f in lire_fiches(domaine=DOMAINE, business_object=OBJET):
    print(f'{f["nom"]} | statut={f["statut"]} | suivant={f["acteur_suivant"]} | rejets={f["nb_rejets"]} | liens={f["colonnes_liees"]}')

print("\nParcours complet de « Lot de production » :")
print(lire_fiches(id="GLO-01")[0]["commentaire_ia"])