"""AG-GRP-STEWARD — agent rédacteur du standard groupe (assiste le Data Steward).

Rédige la définition (et la formule d'un KPI) des fiches d'un Business Object du glossaire.
Ne fait ni les liens avec les colonnes (croisement B→A), ni la classification (agent DPO).
Circuit : Rédacteur → Croisement B→A → Agent DPO → Leader → Owner → Data Owner humain.
"""
import json

from commun.outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "groupe"
AGENT = "AG-GRP-STEWARD"
SUIVANT = "AG-GRP-CROISEMENT-BA"
utiliser_standard(STANDARD)   # cet agent ne travaille que dans le standard groupe


def documenter_business_object(domaine, business_object):
    """Rédige les fiches d'un Business Object (nouvelles ou à corriger), puis relais au croisement B→A."""
    acteurs = infos_domaine(domaine)   # erreur claire si le domaine n'est pas dans le registre du groupe
    regles = charger_regles()
    fiches = [
        f for f in lire_fiches(domaine=domaine, business_object=business_object, chemin="B")
        if f["statut"] in ("Identifié", "À corriger")
    ]
    if not fiches:
        print(f"{AGENT} : aucune fiche à rédiger pour {business_object}.")
        return

    elements = [{"id": f["id"], "type": f["type"], "nom": f["nom"],
                 "definition_precedente": f["definition"] or "", "motif_rejet": f["motif_rejet"] or ""} for f in fiches]

    consigne = f"""Tu es l'assistant du Data Steward ({acteurs["data_steward"]}) du domaine {domaine} dans une entreprise.
Tu rédiges les fiches du Business Object « {business_object} » du glossaire métier.

Règles de la charte du standard groupe :
- definition : {regles["regle_definition"]}
- formule : pour un KPI, une formule de calcul précise (attributs, dates, unités) ; sinon chaîne vide
- Si un motif_rejet est fourni, corrige ta proposition (definition_precedente) en conséquence.

Éléments à rédiger : {json.dumps(elements, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, definition, formule, justification."""

    print(f"{AGENT} : rédaction de {len(fiches)} fiche(s) pour « {business_object} »…")
    propositions = {p.get("id"): p for p in demander_gemini(consigne) if isinstance(p, dict)}

    for f in fiches:
        p = propositions.get(f["id"])
        if p is None:
            print(f"  {f['id']} : pas de réponse de Gemini, la fiche reste en attente.")
            continue
        mettre_a_jour(f["id"], AGENT, "Rédaction proposée", {
            "definition": p.get("definition", ""),
            "formule": p.get("formule", ""),
            "commentaire_ia": "Rédaction proposée par IA. " + p.get("justification", ""),
            "statut": "En rédaction",
            "acteur_suivant": SUIVANT,
        }, detail=p.get("justification", ""))
    print(f"{AGENT} : rédaction terminée, relais à {SUIVANT}.")
