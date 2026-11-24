"""Test complet du standard bis, avec le VRAI Gemini (ou --hors-ligne pour le faux).

    python -m standard_bis.test_standard              (≈ 8 à 20 appels Gemini, 1 Business Object)
    python -m standard_bis.test_standard --hors-ligne (aucun appel, pour vérifier la mécanique)

Parcourt tout le circuit du bis sur « Fournisseur » (domaine Finance, avec la colonne IBAN) : rédaction, croisements,
agent DPO et tri par criticité, Leader bis sur les fiches critiques, dossier du Manager sur les autres,
puis décisions humaines simulées dans le catalogue web (confirmation, publication, renvoi).
Attention : remet à zéro la base du standard bis.
"""
import sys

import commun.outils as o
from commun.lanceur import faire_tourner
from commun.verifications import Controles, controles_communs, decision_web, preparer_test
from standard_bis.lancer import ETAPES_PAR_BO, ETAPES_PAR_DOMAINE

DOMAINE, BO = "Finance", "Fournisseur"
AGENTS = [f"standard_bis.agents.{n}" for n in ("manager", "croisement_b_vers_a", "croisement_a_vers_b", "dpo", "leader_bis")]

preparer_test(AGENTS)
faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)

c = Controles("standard bis")
traitees = controles_communs(c, DOMAINE, BO)
manager = f"Data Manager : {o.infos_domaine(DOMAINE)['data_manager']} (humain)"
leader_humain = "Data Governance Leader (humain)"
actives = [f for f in traitees if f["statut"] not in ("À corriger", "Bloqué")]
critiques = [f for f in actives if f["critique"] == "Oui"]
non_critiques = [f for f in actives if f["critique"] == "Non"]

print("\n— Tri par criticité (propre au bis) —")
c.verifier(f"Fiches critiques → « En confirmation » chez le Leader humain ({len(critiques)})",
           all(f["statut"] == "En confirmation" and f["acteur_suivant"] == leader_humain for f in critiques))
c.verifier(f"Fiches non critiques → Data Manager, sans passer par le Leader ({len(non_critiques)})",
           all(f["acteur_suivant"] == manager and "Contrôle Leader" not in (f["commentaire_ia"] or "") for f in non_critiques))
c.verifier("Leader bis : chaque fiche critique a sa grille C1-C7",
           all("Contrôle Leader : C1" in (f["commentaire_ia"] or "") for f in critiques))
c.verifier("Manager : chaque fiche non critique a son dossier de décision",
           all("Dossier de décision" in (f["commentaire_ia"] or "") for f in non_critiques))
iban = next((f for f in traitees if "IBAN" in (f["nom"] or "")), None)
c.verifier("La colonne IBAN (coordonnées bancaires) est classée critique", iban and iban["critique"] == "Oui")

print("\n— Décisions humaines simulées dans le catalogue web —")
if critiques:
    f = decision_web("bis", critiques[0]["id"], "confirmer", "Confirmé par le test")
    c.verifier(f"Leader humain confirme {critiques[0]['id']} : la fiche passe au Data Manager", f["acteur_suivant"] == manager)
if non_critiques:
    f = decision_web("bis", non_critiques[0]["id"], "publier", "Validé par le test")
    c.verifier(f"Data Manager publie {non_critiques[0]['id']} : statut Certifié", f["statut"] == "Certifié")
colonne = next((f for f in non_critiques[1:] + critiques[1:] if f["chemin"] == "A"), None)
if colonne:
    f = decision_web("bis", colonne["id"], "renvoyer", "Merci de revoir le terme rattaché")
    c.verifier(f"Renvoi de {colonne['id']} : « À corriger » chez le croisement A→B",
               f["statut"] == "À corriger" and f["acteur_suivant"] == "AG-BIS-CROISEMENT-AB")
    faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)
    f = o.lire_fiches(id=colonne["id"])[0]
    c.verifier(f"Après correction, {colonne['id']} revient à un humain (ou reste tracé « À corriger »)",
               (f["acteur_suivant"] or "").endswith("(humain)") or f["statut"] in ("À corriger", "Bloqué"), f"{f['statut']} / {f['acteur_suivant']}")

sys.exit(c.conclure())
