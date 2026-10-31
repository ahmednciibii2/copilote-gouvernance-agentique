import json

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-BIS-MANAGER"


def est_critique(p):
    """Règle de criticité du Leader, appliquée par le code (pas par l'IA)."""
    return p.get("gxp") == "Oui" or p.get("donnee_personnelle") == "Oui" or p.get("confidentialite") == "Restreint"


def traiter_business_object(domaine, business_object):
    """Rédige, classifie et s'auto-contrôle (standard bis), puis route selon la criticité."""
    infos = infos_domaine(domaine)
    if infos["standard"] != "bis":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard bis, rien à faire.")
        return

    manager = infos["data_manager"]
    regles = charger_regles()
    fiches = [
        f for f in lire_fiches(domaine=domaine, business_object=business_object)
        if f["statut"] in ("Identifié", "À corriger")
    ]
    if not fiches:
        print(f"{AGENT} : aucune fiche à traiter pour {business_object}.")
        return

    elements = [{"id": f["id"], "type": f["type"], "nom": f["nom"], "motif_rejet": f["motif_rejet"] or ""} for f in fiches]
    colonnes = [{"id": c["id"], "nom": c["nom"], "exemples": c["exemples"]} for c in lire_fiches(domaine=domaine, chemin="A")]

    consigne = f"""Tu es l'assistant de {manager}, Data Manager du domaine {domaine} dans un laboratoire pharmaceutique.
Tu documentes le Business Object « {business_object} » du glossaire métier, puis tu vérifies toi-même ton travail.

Règles du standard de documentation :
- Définition : {regles["regle_definition"]}
- Confidentialité : une valeur parmi {regles["classification"]["confidentialite"]} (des coordonnées bancaires sont "Restreint")
- donnee_personnelle : "Oui" ou "Non"
- gxp : "Oui" si l'élément sert à garantir la qualité, la traçabilité ou la sécurité du médicament, sinon "Non"
- formule : pour un KPI, une formule de calcul simple ; sinon chaîne vide
- colonnes_liees : liste des id de colonnes techniques ci-dessous qui représentent cet élément ; une colonne qui relève d'un autre Business Object est interdite ; liste vide si aucune
- Champs obligatoires à vérifier : {json.dumps(regles["champs_obligatoires"], ensure_ascii=False)}
- Si un motif_rejet est fourni, corrige ta proposition en conséquence.

Éléments à documenter : {json.dumps(elements, ensure_ascii=False)}
Colonnes techniques du domaine : {json.dumps(colonnes, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, definition, formule, confidentialite, donnee_personnelle, gxp, colonnes_liees, justification."""

    print(f"{AGENT} : envoi de {len(fiches)} fiches à Gemini pour « {business_object} » ({domaine})…")
    nb_critiques = 0
    for p in demander_gemini(consigne):
        critique = est_critique(p)
        champs = {
            "definition": p.get("definition", ""),
            "formule": p.get("formule", ""),
            "confidentialite": p.get("confidentialite", ""),
            "donnee_personnelle": p.get("donnee_personnelle", ""),
            "gxp": p.get("gxp", ""),
            "colonnes_liees": ", ".join(p.get("colonnes_liees", [])),
            "critique": "Oui" if critique else "Non",
        }
        if critique:
            nb_critiques += 1
            champs.update({
                "statut": "En confirmation",
                "acteur_suivant": "AG-BIS-LEADER",
                "commentaire_ia": "Proposé par IA. Élément critique selon la règle du Leader : confirmation requise. " + p.get("justification", ""),
            })
        else:
            champs.update({
                "statut": "À valider",
                "acteur_suivant": f"Data Manager : {manager} (humain)",
                "commentaire_ia": "Proposé par IA, non critique : prêt pour validation par le Data Manager. " + p.get("justification", ""),
            })
        mettre_a_jour(p["id"], AGENT, "Rédaction, classification et auto-contrôle", champs, detail=p.get("justification", ""))
    print(f"{AGENT} : {nb_critiques} fiche(s) critique(s) envoyée(s) à AG-BIS-LEADER, les autres prêtes pour {manager}.")