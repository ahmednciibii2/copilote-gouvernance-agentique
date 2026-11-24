"""Test complet du standard groupe, avec le VRAI Gemini (ou --hors-ligne pour le faux).

    python -m standard_groupe.test_standard              (≈ 8 à 20 appels Gemini, 1 Business Object)
    python -m standard_groupe.test_standard --hors-ligne (aucun appel, pour vérifier la mécanique)

Parcourt tout le circuit du groupe sur « Lot de production » : rédaction, croisements B→A et A→B, agent DPO,
Leader (grille C1-C7), tours de correction, dossier de l'Owner, puis décisions humaines simulées dans le catalogue web.
Attention : remet à zéro la base du standard groupe.
"""
import sys

import commun.outils as o
from commun.lanceur import faire_tourner
from commun.verifications import Controles, controles_communs, decision_web, preparer_test
from standard_groupe.lancer import ETAPES_PAR_BO, ETAPES_PAR_DOMAINE

DOMAINE, BO = "Supply Chain", "Lot de production"
AGENTS = [f"standard_groupe.agents.{n}" for n in ("steward", "croisement_b_vers_a", "croisement_a_vers_b", "dpo", "leader", "owner")]

preparer_test(AGENTS)
faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)

c = Controles("standard groupe")
traitees = controles_communs(c, DOMAINE, BO)
humain = f"Data Owner : {o.infos_domaine(DOMAINE)['data_owner']} (humain)"
en_attente = [f for f in traitees if f["acteur_suivant"] == humain]

print("\n— Leader et Owner (propres au groupe) —")
c.verifier("Leader : toutes les fiches traitées sont passées par la grille C1-C7",
           all("Contrôle Leader : C1" in (f["commentaire_ia"] or "") for f in traitees if f["statut"] not in ("À corriger", "Bloqué")))
bloquees = [f for f in traitees if f["statut"] == "Bloqué"]
if bloquees:
    c.verifier(f"Blocage : {len(bloquees)} fiche(s) refusée(s) trop de fois → arbitrage du Data Governance Leader humain",
               all(f["acteur_suivant"] == "Data Governance Leader (humain)" for f in bloquees))
c.verifier("Owner : chaque fiche en attente du Data Owner a son dossier de décision",
           en_attente and all("Dossier de décision" in (f["commentaire_ia"] or "") for f in en_attente), f"{len(en_attente)} fiche(s)")

print("\n— Décisions humaines simulées dans le catalogue web —")
terme = next((f for f in en_attente if f["chemin"] == "B"), None)
colonne = next((f for f in en_attente if f["chemin"] == "A"), None)
if terme:
    f = decision_web("groupe", terme["id"], "publier", "Validé par le test")
    c.verifier(f"Data Owner publie {terme['id']} : statut Certifié", f["statut"] == "Certifié")
if colonne:
    f = decision_web("groupe", colonne["id"], "renvoyer", "Merci de revoir le terme rattaché")
    c.verifier(f"Data Owner renvoie {colonne['id']} : « À corriger » chez le croisement A→B",
               f["statut"] == "À corriger" and f["acteur_suivant"] == "AG-GRP-CROISEMENT-AB")
    faire_tourner([(DOMAINE, [BO])], ETAPES_PAR_BO, ETAPES_PAR_DOMAINE)
    f = o.lire_fiches(id=colonne["id"])[0]
    c.verifier(f"Après correction, {colonne['id']} revient au Data Owner (ou reste tracé « À corriger »)",
               f["acteur_suivant"] == humain or f["statut"] in ("À corriger", "Bloqué"), f"{f['statut']} / {f['acteur_suivant']}")

sys.exit(c.conclure())
