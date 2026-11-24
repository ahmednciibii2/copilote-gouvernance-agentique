"""AG-BIS-CROISEMENT-BA — croisement B→A du standard bis (tâche M4 du Data Manager).

Part d'un terme ou d'un KPI du glossaire (chemin B) et cherche les colonnes techniques qui le représentent.
- Colonnes trouvées : le lien est écrit dans colonnes_liees.
- Aucune colonne : écart B→A signalé (pas de refus), le décideur humain arbitrera.
Relais ensuite à l'agent DPO pour la classification.
"""
import json

from commun.outils import demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "bis"
AGENT = "AG-BIS-CROISEMENT-BA"
SUIVANT = "AG-BIS-DPO"
utiliser_standard(STANDARD)


def interpreter_liens(proposition, colonnes_connues):
    """Garde seulement les id de colonnes qui existent ; renvoie (liste des liens, commentaire)."""
    liens = [i for i in proposition.get("colonnes_liees", []) if i in colonnes_connues]
    inconnus = [i for i in proposition.get("colonnes_liees", []) if i not in colonnes_connues]
    if liens:
        texte = "Croisement B→A : lié à " + ", ".join(f"{i} ({colonnes_connues[i]})" for i in liens) + "."
    else:
        texte = "Croisement B→A : écart B→A, aucune colonne correspondante dans le SI."
    if inconnus:
        texte += " Colonnes inconnues ignorées : " + ", ".join(inconnus) + "."
    return liens, texte


def relier_termes(domaine):
    """Relie chaque terme ou KPI en attente à ses colonnes techniques, puis relais à l'agent DPO."""
    acteurs = infos_domaine(domaine)
    fiches = [f for f in lire_fiches(domaine=domaine, chemin="B", statut="En rédaction") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucun terme à relier pour {domaine}.")
        return

    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    exemples = [{"id": c["id"], "nom": c["nom"], "exemples": c["exemples"]} for c in lire_fiches(domaine=domaine, chemin="A")]
    termes = [{"id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
               "definition": f["definition"], "motif_rejet": f["motif_rejet"] or ""} for f in fiches]

    consigne = f"""Tu es l'assistant du Data Manager ({acteurs["data_manager"]}) du domaine {domaine} dans une entreprise.
Pour chaque élément du glossaire, trouve les colonnes techniques du SI qui le représentent réellement.
- colonnes_liees : liste des id de colonnes ci-dessous ; liste vide si aucune ne convient (c'est un écart normal, pas une erreur).
- Une colonne qui relève d'un autre Business Object ne doit pas être liée.
- Un Business Object n'a en général pas de colonne propre : liste vide.
- Si un motif_rejet est fourni, corrige en conséquence.

Éléments du glossaire : {json.dumps(termes, ensure_ascii=False)}
Colonnes techniques du domaine : {json.dumps(exemples, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, colonnes_liees, justification."""

    print(f"{AGENT} : croisement B→A de {len(fiches)} élément(s) du domaine {domaine}…")
    propositions = {p.get("id"): p for p in demander_gemini(consigne) if isinstance(p, dict)}

    nb_ecarts = 0
    for f in fiches:
        p = propositions.get(f["id"])
        if p is None:
            print(f"  {f['id']} : pas de réponse de Gemini, la fiche reste en attente.")
            continue
        liens, texte = interpreter_liens(p, colonnes)
        nb_ecarts += 0 if liens else 1
        mettre_a_jour(f["id"], AGENT, "Croisement B→A proposé", {
            "colonnes_liees": ", ".join(liens),
            "commentaire_ia": (f["commentaire_ia"] or "") + " | " + texte,
            "acteur_suivant": SUIVANT,
        }, detail=texte)
    print(f"{AGENT} : croisement B→A terminé ({nb_ecarts} écart(s) B→A), relais à {SUIVANT}.")
