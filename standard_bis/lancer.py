"""Lanceur du standard bis — à lancer depuis la racine du projet :

    python -m standard_bis.lancer                                      (tout, base remise à zéro)
    python -m standard_bis.lancer --domaine "Finance" --bo "Fournisseur"
    python -m standard_bis.lancer --reprise                            (sans remise à zéro)

Circuit : Manager (rédaction) → Croisement B→A → Croisement A→B → Agent DPO (tri par criticité)
          → critique : Leader bis (C1-C7) → Data Governance Leader humain
          → non critique : Manager (dossier) → Data Manager humain, dans le catalogue web.
"""
from commun.lanceur import executer
from standard_bis.agents import croisement_a_vers_b, croisement_b_vers_a, dpo, leader_bis, manager

if __name__ == "__main__":
    executer(
        "bis",
        etapes_par_bo=[manager.documenter_business_object],
        etapes_par_domaine=[
            croisement_b_vers_a.relier_termes,
            croisement_a_vers_b.rattacher_colonnes,
            dpo.classifier,
            leader_bis.confirmer,
            manager.preparer_decision,
        ],
    )
