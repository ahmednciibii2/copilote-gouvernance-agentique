"""Outils communs des tests complets par standard (test_standard.py) : contrôles ✅ / ❌ et préparation.

Les contrôles ci-dessous vérifient la STRUCTURE du résultat (et non le texte exact rédigé par Gemini,
qui varie d'un lancement à l'autre) : tout est traité, les liens et écarts sont signalés, la classification
respecte la charte et l'héritage, aucune fiche n'est perdue, tout est tracé.
"""
import importlib
import sys

import commun.outils as o
from commun.creer_base import initialiser
from commun.generer_donnees import generer


class Controles:
    def __init__(self, titre):
        self.titre, self.lignes = titre, []

    def verifier(self, libelle, ok, detail=""):
        self.lignes.append((libelle, bool(ok), detail))
        print(("  ✅ " if ok else "  ❌ ") + libelle + ("" if ok or not detail else f"  → {detail}"))

    def conclure(self):
        nb_ok = sum(ok for _, ok, _ in self.lignes)
        print(f"\n{nb_ok}/{len(self.lignes)} contrôles réussis — {self.titre}")
        return 0 if nb_ok == len(self.lignes) else 1


def preparer_test(modules_agents):
    """Option --hors-ligne : remplace Gemini par le faux Gemini. Puis recrée la base du standard actif."""
    hors_ligne = "--hors-ligne" in sys.argv
    if hors_ligne:
        from commun.faux_gemini import faux_gemini
        for nom in modules_agents:
            importlib.import_module(nom).demander_gemini = faux_gemini
    print(f"=== Test complet du standard {o.STANDARD} ({'faux Gemini, hors ligne' if hors_ligne else 'VRAI Gemini'}) ===")
    print("Attention : la base du standard est remise à zéro par ce test.\n")
    if not (o.chemin("donnees") / "glossaire_metier.xlsx").exists():
        generer()
    print(f"Base créée : {o.BASE.relative_to(o.RACINE)} ({initialiser()} fiches)")


def rang(axe, valeur, regles):
    ordre = regles["classification"][axe]
    return ordre.index(valeur) if valeur in ordre else -1


def controles_communs(c, domaine, bo):
    """Contrôles valables pour les deux standards. Renvoie les fiches traitées (termes du BO + colonnes du domaine)."""
    regles = o.charger_regles()
    toutes = {f["id"]: f for f in o.lire_fiches(domaine=domaine)}
    termes = [f for f in toutes.values() if f["chemin"] == "B" and f["business_object"] == bo]
    colonnes = [f for f in toutes.values() if f["chemin"] == "A"]
    traitees = termes + colonnes
    elements = [t for t in termes if t["type"] in ("Business Term", "KPI")]

    print("\n— Rédaction et croisements —")
    c.verifier("Rédaction : toutes les fiches du Business Object ont quitté « Identifié »",
               all(t["statut"] != "Identifié" for t in termes), [t["id"] for t in termes if t["statut"] == "Identifié"])
    c.verifier("Rédaction : chaque fiche du Business Object a une définition",
               all(t["definition"] for t in termes), [t["id"] for t in termes if not t["definition"]])
    c.verifier("B→A : chaque terme ou KPI a des colonnes liées OU un écart B→A signalé",
               all(t["colonnes_liees"] or "écart B→A" in (t["commentaire_ia"] or "") for t in elements))
    c.verifier("B→A : au moins un lien terme → colonne trouvé", any(t["colonnes_liees"] for t in elements))
    c.verifier("A→B : chaque colonne du domaine est rattachée (terme existant ou NOUVEAU)",
               all(col["terme_lie"] and (col["terme_lie"] in toutes or col["terme_lie"].startswith("NOUVEAU")) for col in colonnes),
               [col["id"] for col in colonnes if not col["terme_lie"]])

    c.verifier("Custodian : chaque colonne a sa description technique, son lignage et sa règle qualité",
               all(col["description_technique"] and col["lignage"] and col["regle_qualite"] for col in colonnes),
               [col["id"] for col in colonnes if not (col["description_technique"] and col["regle_qualite"])])

    print("\n— Agent DPO —")
    classees = [f for f in traitees if f["heritage"]]
    c.verifier("DPO : toutes les fiches traitées sont classifiées", len(classees) == len(traitees),
               [f["id"] for f in traitees if not f["heritage"]])
    c.verifier("DPO : valeurs de classification conformes à la charte",
               all(f[a] in regles["classification"][a] for f in classees for a in ("confidentialite", "donnee_personnelle", "reglementee")))
    heritees = [f for f in classees if f["heritage"].startswith("héritée de ")]
    erreurs = []
    for col in heritees:
        terme = toutes.get(col["heritage"].split()[2])
        if terme and any(rang(a, col[a], regles) < rang(a, terme[a], regles) for a in ("confidentialite", "donnee_personnelle", "reglementee")):
            erreurs.append(col["id"])
    c.verifier(f"DPO : héritage respecté, chaque colonne au moins aussi stricte que son terme ({len(heritees)} colonne(s) héritée(s))",
               not erreurs, erreurs)
    critique = lambda f: f["reglementee"] == "Oui" or f["donnee_personnelle"] == "Oui" or f["confidentialite"] == "Restreint"
    c.verifier("DPO : criticité conforme à la règle de la charte",
               all((f["critique"] == "Oui") == critique(f) for f in classees))

    print("\n— Circuit et traçabilité —")
    perdues = [f["id"] for f in traitees if not ((f["acteur_suivant"] or "").endswith("(humain)") or f["statut"] in ("À corriger", "Bloqué"))]
    c.verifier("Circuit : aucune fiche restée bloquée chez un agent", not perdues, perdues)
    con = o.connexion()
    sans_trace = [f["id"] for f in traitees
                  if con.execute("SELECT COUNT(*) FROM historique WHERE fiche_id = ?", (f["id"],)).fetchone()[0] < 3]
    con.close()
    c.verifier("Traçabilité : chaque fiche traitée a au moins 3 étapes dans l'historique", not sans_trace, sans_trace)
    return traitees


def decision_web(standard, fiche_id, action, motif=""):
    """Simule un clic dans le catalogue web (même code que le navigateur)."""
    import catalogue_web
    base = o.BASE
    catalogue_web.app.test_client().post(f"/{standard}/fiche/{fiche_id}/decision", data={"action": action, "motif": motif})
    o.utiliser_standard(standard)
    o.BASE = base
    return o.lire_fiches(id=fiche_id)[0]
