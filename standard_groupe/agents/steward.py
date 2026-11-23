import json

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-GRP-STEWARD"


def documenter_business_object(domaine, business_object):
    """Rédige et classifie toutes les fiches d'un Business Object (standard groupe)."""
    if infos_domaine(domaine)["standard"] != "groupe":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard groupe, rien à faire.")
        return

    regles = charger_regles()
    fiches = [
        f for f in lire_fiches(domaine=domaine, business_object=business_object)
        if f["statut"] in ("Identifié", "À corriger")
    ]
    if not fiches:
        print(f"{AGENT} : aucune fiche à documenter pour {business_object}.")
        return

    elements = [{"id": f["id"], "type": f["type"], "nom": f["nom"], "motif_rejet": f["motif_rejet"] or ""} for f in fiches]
    colonnes = [{"id": c["id"], "nom": c["nom"], "exemples": c["exemples"]} for c in lire_fiches(domaine=domaine, chemin="A")]

    consigne = f"""Tu es l'assistant du Data Steward du domaine {domaine} dans un laboratoire pharmaceutique.
Tu documentes le Business Object « {business_object} » du glossaire métier.

Règles du standard de documentation :
- Définition : {regles["regle_definition"]}
- Confidentialité : une valeur parmi {regles["classification"]["confidentialite"]}
- donnee_personnelle : "Oui" ou "Non"
- gxp : "Oui" si l'élément sert à garantir la qualité, la traçabilité ou la sécurité du médicament, sinon "Non"
- formule : pour un KPI, une formule de calcul simple ; sinon chaîne vide
- colonnes_liees : liste des id de colonnes techniques ci-dessous qui représentent cet élément dans le SI ; liste vide si aucune
- Si un motif_rejet est fourni, corrige ta proposition en conséquence.

Éléments à documenter : {json.dumps(elements, ensure_ascii=False)}
Colonnes techniques du domaine : {json.dumps(colonnes, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, definition, formule, confidentialite, donnee_personnelle, gxp, colonnes_liees, justification."""

    print(f"{AGENT} : envoi de {len(fiches)} fiches à Gemini pour « {business_object} »…")
    propositions = demander_gemini(consigne)

    for p in propositions:
        mettre_a_jour(
            p["id"],
            AGENT,
            "Proposition de documentation",
            {
                "definition": p.get("definition", ""),
                "formule": p.get("formule", ""),
                "confidentialite": p.get("confidentialite", ""),
                "donnee_personnelle": p.get("donnee_personnelle", ""),
                "gxp": p.get("gxp", ""),
                "colonnes_liees": ", ".join(p.get("colonnes_liees", [])),
                "commentaire_ia": "Proposé par IA, à valider. " + p.get("justification", ""),
                "statut": "À valider",
                "acteur_suivant": "AG-GRP-LEADER",
            },
            detail=p.get("justification", ""),
        )
    print(f"{AGENT} : {len(propositions)} fiches passées en « À valider », relais à AG-GRP-LEADER.")
