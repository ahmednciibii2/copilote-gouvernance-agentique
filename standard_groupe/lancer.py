"""Lanceur du standard groupe — à lancer depuis la racine du projet :

    python -m standard_groupe.lancer                                   (tout, base remise à zéro)
    python -m standard_groupe.lancer --domaine "Supply Chain" --bo "Lot de production"
    python -m standard_groupe.lancer --reprise                         (sans remise à zéro)

Circuit : Steward (rédaction) → Croisement B→A → Croisement A→B → Agent DPO → Leader (C1-C7) → Owner (dossier)
          → Data Owner humain, dans le catalogue web.
"""
from commun.lanceur import executer
from standard_groupe.agents import croisement_a_vers_b, croisement_b_vers_a, dpo, leader, owner, steward

if __name__ == "__main__":
    executer(
        "groupe",
        etapes_par_bo=[steward.documenter_business_object],
        etapes_par_domaine=[
            croisement_b_vers_a.relier_termes,
            croisement_a_vers_b.rattacher_colonnes,
            dpo.classifier,
            leader.controler,
            owner.preparer_decision,
        ],
    )
