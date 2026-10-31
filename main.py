import os
import time

import outils
from agents.agent_bis_leader import confirmer
from agents.agent_bis_manager import traiter_business_object
from agents.agent_grp_leader import controler
from agents.agent_grp_owner import preparer_decision
from agents.agent_grp_steward import documenter_business_object
from agents.croisement_a_vers_b import rattacher_colonnes
from creer_base import initialiser

SCENARIOS = [
    ("groupe", "catalogue_groupe.db", "donnees/registre_standard_groupe.xlsx"),
    ("bis", "catalogue_bis.db", "donnees/registre_standard_bis.xlsx"),
]
DOMAINES = ["Finance", "Supply Chain"]


def objets(domaine):
    """Liste des Business Objects du glossaire d'un domaine."""
    return sorted({f["business_object"] for f in outils.lire_fiches(domaine=domaine, chemin="B")})


def bilan(nom):
    """Affiche l'état du catalogue et les écarts détectés, et l'enregistre dans rapports/."""
    fiches = outils.lire_fiches()
    lignes = [f"===== Bilan du scénario standard {nom} ====="]
    compte = {}
    for f in fiches:
        cle = (f["statut"], f["acteur_suivant"] or "")
        compte[cle] = compte.get(cle, 0) + 1
    for (statut, suivant), n in sorted(compte.items()):
        lignes.append(f"  {n:>2} fiche(s) | {statut} | {suivant}")

    ecarts_b = [f["nom"] for f in fiches if f["chemin"] == "B" and f["type"] in ("Business Term", "KPI") and not f["colonnes_liees"]]
    ecarts_a = [f'{f["nom"]} → {f["terme_lie"]}' for f in fiches if f["chemin"] == "A" and (f["terme_lie"] or "").startswith("NOUVEAU")]
    bloquees = [f'{f["nom"]} : {f["motif_rejet"]}' for f in fiches if f["statut"] == "Bloqué"]

    lignes.append("  Écarts B→A (termes sans colonne dans le SI) : " + (", ".join(ecarts_b) or "aucun"))
    lignes.append("  Écarts A→B (colonnes sans terme métier) :")
    lignes += [f"    - {e}" for e in (ecarts_a or ["aucun"])]
    lignes.append("  Fiches bloquées (arbitrage du Leader humain) :")
    lignes += [f"    - {b}" for b in (bloquees or ["aucune"])]

    texte = "\n".join(lignes)
    print("\n" + texte)
    os.makedirs("rapports", exist_ok=True)
    with open(f"rapports/bilan_{nom}.txt", "w", encoding="utf-8") as fichier:
        fichier.write(texte)


debut = time.time()
tours = outils.charger_regles()["max_allers_retours"] + 1

for nom, base, registre in SCENARIOS:
    print(f"\n########## Scénario : standard {nom} ##########")
    outils.utiliser(base, registre)
    print("Base réinitialisée :", initialiser(base), "fiches")

    for domaine in DOMAINES:
        for tour in range(1, tours + 1):
            print(f"\n--- {domaine} : tour {tour} ---")
            for objet in objets(domaine):
                if nom == "groupe":
                    documenter_business_object(domaine, objet)
                else:
                    traiter_business_object(domaine, objet)
            rattacher_colonnes(domaine)
            if nom == "groupe":
                controler(domaine)
            else:
                confirmer(domaine)
            if not outils.lire_fiches(domaine=domaine, statut="À corriger"):
                break
        if nom == "groupe":
            preparer_decision(domaine)

    bilan(nom)

print(f"\nDurée totale : {round((time.time() - debut) / 60, 1)} min")
print("Bilans enregistrés dans rapports/bilan_groupe.txt et rapports/bilan_bis.txt")