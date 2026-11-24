"""Test complet du standard groupe, avec le VRAI Gemini (ou --hors-ligne pour le faux).

    python -m standard_groupe.test_standard              (≈ 8 à 20 appels Gemini, 1 Business Object)
    python -m standard_groupe.test_standard --hors-ligne (aucun appel, pour vérifier la mécanique)

Parcourt tout le circuit du groupe sur « Lot de production » : rédaction, documentation technique (Custodian),
croisements B→A et A→B, agent DPO, Leader (grille C1-C7), tours de correction, dossiers de l'Owner et du Custodian, puis décisions humaines simulées dans le catalogue web.
Attention : remet à zéro la base du standard groupe.
"""
import sys

import commun.outils as o
from commun.lanceur import faire_tourner
from commun.verifications import Controles, controles_communs, decision_web, preparer_test
from standard_groupe.lancer import ETAPES_PAR_BO, ETAPES_PAR_DOMAINE

DOMAINE, BO = "Supply Chain", "Lot de production"
AGENTS = [f"standard_groupe.agents.{n}" for n in ("steward", "custodian", "croisement_b_vers_a", "croisement_a_vers_b", "dpo", "leader", "owner")]

preparer_test(AGENTS)
faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)

c = Controles("standard groupe")
traitees = controles_communs(c, DOMAINE, BO)
acteurs = o.infos_domaine(DOMAINE)
humain = f"Data Owner : {acteurs['data_owner']} (humain)"
custodian_humain = f"Data Custodian : {acteurs['data_custodian']} (humain)"
en_attente = [f for f in traitees if f["acteur_suivant"] == humain]
colonnes_attente = [f for f in traitees if f["acteur_suivant"] == custodian_humain]

print("\n— Leader, Owner et Custodian (groupe) —")
c.verifier("Leader : toutes les fiches traitées sont passées par la grille C1-C7",
           all("Contrôle Leader : C1" in (f["commentaire_ia"] or "") for f in traitees if f["statut"] not in ("À corriger", "Bloqué")))
bloquees = [f for f in traitees if f["statut"] == "Bloqué"]
if bloquees:
    c.verifier(f"Blocage : {len(bloquees)} fiche(s) refusée(s) trop de fois → arbitrage du Data Governance Leader humain",
               all(f["acteur_suivant"] == "Data Governance Leader (humain)" for f in bloquees))
c.verifier("Les termes attendent le Data Owner, les colonnes le Data Custodian",
           all(f["chemin"] == "B" for f in en_attente) and all(f["chemin"] == "A" for f in colonnes_attente) and colonnes_attente,
           f"{len(en_attente)} terme(s), {len(colonnes_attente)} colonne(s)")
c.verifier("Owner : chaque terme en attente du Data Owner a son dossier de décision",
           en_attente and all("Dossier de décision" in (f["commentaire_ia"] or "") for f in en_attente))
c.verifier("Custodian : chaque colonne en attente du Data Custodian a son dossier de décision",
           colonnes_attente and all("Dossier de décision" in (f["commentaire_ia"] or "") for f in colonnes_attente))

print("\n— Décisions humaines simulées dans le catalogue web —")
if en_attente:
    f = decision_web("groupe", en_attente[0]["id"], "publier", "Validé par le test")
    c.verifier(f"Data Owner publie {en_attente[0]['id']} : statut Certifié", f["statut"] == "Certifié")
if colonnes_attente:
    f = decision_web("groupe", colonnes_attente[0]["id"], "publier", "Documentation technique validée")
    c.verifier(f"Data Custodian publie {colonnes_attente[0]['id']} : statut Certifié", f["statut"] == "Certifié")
if len(colonnes_attente) > 1:
    colonne = colonnes_attente[1]
    f = decision_web("groupe", colonne["id"], "renvoyer", "Merci de préciser la règle qualité")
    c.verifier(f"Data Custodian renvoie {colonne['id']} : « À corriger » chez l'agent Custodian",
               f["statut"] == "À corriger" and f["acteur_suivant"] == "AG-GRP-CUSTODIAN")
    faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)
    f = o.lire_fiches(id=colonne["id"])[0]
    c.verifier(f"Après correction, {colonne['id']} revient au Data Custodian (ou reste tracé « À corriger » / « Bloqué »)",
               f["acteur_suivant"] == custodian_humain or f["statut"] in ("À corriger", "Bloqué"), f"{f['statut']} / {f['acteur_suivant']}")

sys.exit(c.conclure())
