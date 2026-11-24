"""Test HORS LIGNE du circuit complet d'un standard, avec un faux Gemini (aucun appel réseau, aucun quota).

Usage, depuis la racine du projet :
    python -m commun.test_circuit_hors_ligne groupe
    python -m commun.test_circuit_hors_ligne bis

Il crée une base temporaire (la vraie base du standard n'est pas touchée), fait passer le Business Object
« Lot de production » dans tout le circuit, puis vérifie les points clés avec ✅ ou ❌.
"""
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import commun.outils as o

STD = sys.argv[1] if len(sys.argv) > 1 else "groupe"
o.utiliser_standard(STD)


def faux_gemini(consigne, essais=3):
    """Répond comme Gemini, de façon prévisible, à n'importe quelle consigne des agents."""
    reponses = []
    for i in sorted(set(re.findall(r'"id": "([A-Z]{3}-\d+)"', consigne))):
        r = {"id": i, "definition": f"Définition de test pour {i}.", "formule": "lots refusés / lots fabriqués (mois)", "justification": "test",
             "colonnes_liees": ["TEC-01"] if i == "GLO-02" else [],
             "terme_lie": "GLO-02" if i == "TEC-01" else "NOUVEAU", "nouveau_terme": f"Terme {i}", "business_object": "Lot de production",
             "confidentialite": "Restreint" if i == "TEC-01" else "Interne", "donnee_personnelle": "Non",
             "reglementee": "Oui" if i in ("GLO-02", "TEC-01") else "Non",
             "synthese": "Synthèse de test.", "recommandation": "Valider", "motif": "", "points_attention": ""}
        for p in ("C2", "C3", "C4", "C5"):
            r[p] = {"resultat": "ko" if (i == "GLO-03" and p == "C4") else "ok", "motif": "colonne d'un autre objet" if i == "GLO-03" else ""}
        reponses.append(r)
    return reponses


if STD == "groupe":
    from standard_groupe.agents import croisement_a_vers_b as ab, croisement_b_vers_a as ba, dpo, leader, owner, steward as redacteur
    agents = [redacteur, ba, ab, dpo, leader, owner]
else:
    from standard_bis.agents import croisement_a_vers_b as ab, croisement_b_vers_a as ba, dpo, leader_bis as leader, manager as redacteur
    agents = [redacteur, ba, ab, dpo, leader]
for a in agents:
    a.demander_gemini = faux_gemini

from commun.creer_base import initialiser

o.BASE = Path(tempfile.gettempdir()) / f"test_hors_ligne_{STD}.db"
dossier = o.chemin("donnees")
if not (dossier / "glossaire_metier.xlsx").exists():
    dossier = o.RACINE / "donnees"   # avant l'étape M6, les données sont encore à la racine
print(f"Base temporaire : {o.BASE} ({initialiser(dossier)} fiches chargées depuis {dossier.relative_to(o.RACINE)})\n")

D, BO = "Supply Chain", "Lot de production"
redacteur.documenter_business_object(D, BO)
ba.relier_termes(D)
ab.rattacher_colonnes(D)
dpo.classifier(D)
if STD == "groupe":
    leader.controler(D)
    owner.preparer_decision(D)
else:
    leader.confirmer(D)
    redacteur.preparer_decision(D)

con = sqlite3.connect(o.BASE)
con.row_factory = sqlite3.Row
f = {r["id"]: dict(r) for r in con.execute("SELECT * FROM fiches")}
humain = "Data Owner : DO-SC (humain)" if STD == "groupe" else "Data Manager : DM-SC (humain)"
controles = [
    ("B→A : lien trouvé (GLO-02 → TEC-01)", f["GLO-02"]["colonnes_liees"] == "TEC-01"),
    ("B→A : écart signalé (KPI GLO-06 sans colonne)", "écart B→A" in f["GLO-06"]["commentaire_ia"]),
    ("A→B : lien trouvé (TEC-01 → GLO-02)", f["TEC-01"]["terme_lie"] == "GLO-02"),
    ("A→B : NOUVEAU proposé (TEC-03)", f["TEC-03"]["terme_lie"].startswith("NOUVEAU : ")),
    ("DPO : terme porteur de la classification", f["GLO-02"]["heritage"] == "porteur (terme métier)"),
    ("DPO : héritage + écart (TEC-01 Restreint sous terme Interne)", "écart d'héritage" in f["TEC-01"]["heritage"] and f["TEC-01"]["confidentialite"] == "Restreint"),
    ("DPO : criticité calculée (GLO-02 réglementée)", f["GLO-02"]["critique"] == "Oui"),
]
if STD == "groupe":
    controles += [
        ("Leader : grille C1-C7 écrite", "Contrôle Leader : C1" in f["GLO-02"]["commentaire_ia"]),
        ("Leader : refus C4 → À corriger, retour au Steward (GLO-03)", f["GLO-03"]["statut"] == "À corriger" and f["GLO-03"]["acteur_suivant"] == "AG-GRP-STEWARD"),
        ("Owner : dossier en 5 rubriques", "Contrôle C1-C7 :" in f["GLO-02"]["commentaire_ia"]),
        ("Décision : attend le Data Owner humain", f["GLO-02"]["acteur_suivant"] == humain),
    ]
else:
    controles += [
        ("Tri : fiche critique → En confirmation (GLO-02)", f["GLO-02"]["statut"] == "En confirmation"),
        ("Leader bis : grille C1-C7 écrite sur la fiche critique", "Contrôle Leader : C1" in f["GLO-02"]["commentaire_ia"]),
        ("Leader bis : attend la confirmation du Leader humain", f["GLO-02"]["acteur_suivant"] == "Data Governance Leader (humain)"),
        ("Fiche non critique : pas de contrôle Leader (GLO-03)", "Contrôle Leader" not in f["GLO-03"]["commentaire_ia"]),
        ("Manager : dossier du Data Manager (GLO-03)", "Dossier de décision" in f["GLO-03"]["commentaire_ia"] and f["GLO-03"]["acteur_suivant"] == humain),
    ]
print()
for libelle, ok in controles:
    print(("✅ " if ok else "❌ ") + libelle)
print(f"\n{sum(ok for _, ok in controles)}/{len(controles)} contrôles réussis — standard {STD}")
