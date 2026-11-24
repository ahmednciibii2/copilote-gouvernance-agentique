"""Lanceur du standard groupe — à lancer depuis la racine du projet :

    python -m standard_groupe.lancer                                   (tout, base remise à zéro)
    python -m standard_groupe.lancer --domaine "Supply Chain" --bo "Lot de production"
    python -m standard_groupe.lancer --reprise                         (sans remise à zéro)

Circuit :
  terme   : Steward (rédaction) → Croisement B→A → Agent DPO → Leader (C1-C7) → Owner (dossier) → Data Owner humain
  colonne : Custodian (documentation technique) → Croisement A→B → Agent DPO → Leader (C1-C7)
            → Custodian (dossier) → Data Custodian humain
Les décisions humaines se prennent dans le catalogue web.
"""
from commun.lanceur import executer
from standard_groupe.agents import croisement_a_vers_b, croisement_b_vers_a, custodian, dpo, leader, owner, steward

# Ordre du circuit du standard groupe (réutilisé par test_standard.py)
ETAPES_PAR_BO = [steward.documenter_business_object]
ETAPES_PAR_DOMAINE = [
    custodian.documenter_colonnes,
    croisement_b_vers_a.relier_termes,
    croisement_a_vers_b.rattacher_colonnes,
    dpo.classifier,
    leader.controler,
    owner.preparer_decision,
    custodian.preparer_decision,
]

if __name__ == "__main__":
    executer("groupe", ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)
