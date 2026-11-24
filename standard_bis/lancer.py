"""Lanceur du standard bis — à lancer depuis la racine du projet :

    python -m standard_bis.lancer                                      (tout, base remise à zéro)
    python -m standard_bis.lancer --domaine "Finance" --bo "Fournisseur"
    python -m standard_bis.lancer --reprise                            (sans remise à zéro)

Circuit :
  terme   : Manager (rédaction) → Croisement B→A → Agent DPO (tri par criticité)
  colonne : Custodian (documentation technique) → Croisement A→B → Agent DPO (tri par criticité)
  critique     → Leader bis (C1-C7) → Data Governance Leader humain (confirmation)
                 → Data Manager humain (terme) / Data Custodian humain (colonne)
  non critique → Manager (dossier) → Data Manager humain (terme) ;
                 Custodian (dossier) → Data Custodian humain (colonne)
Les décisions humaines se prennent dans le catalogue web.
"""
from commun.lanceur import executer
from standard_bis.agents import croisement_a_vers_b, croisement_b_vers_a, custodian, dpo, leader_bis, manager

# Ordre du circuit du standard bis (réutilisé par test_standard.py)
ETAPES_PAR_BO = [manager.documenter_business_object]
ETAPES_PAR_DOMAINE = [
    custodian.documenter_colonnes,
    croisement_b_vers_a.relier_termes,
    croisement_a_vers_b.rattacher_colonnes,
    dpo.classifier,
    leader_bis.confirmer,
    manager.preparer_decision,
    custodian.preparer_decision,
]

if __name__ == "__main__":
    executer("bis", ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)
