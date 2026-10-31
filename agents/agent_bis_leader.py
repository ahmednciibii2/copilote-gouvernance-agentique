import json

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-BIS-LEADER"


def confirmer(domaine):
    """Analyse les dossiers critiques du standard bis et recommande ; la confirmation reste humaine."""
    infos = infos_domaine(domaine)
    if infos["standard"] != "bis":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard bis, rien à faire.")
        return

    regles = charger_regles()
    fiches = [f for f in lire_fiches(domaine=domaine, statut="En confirmation") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucun dossier critique à analyser pour {domaine}.")
        return

    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    dossiers = []
    for f in fiches:
        liens = [i.strip() for i in (f["colonnes_liees"] or "").split(",") if i.strip()]
        dossiers.append({
            "id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
            "definition": f["definition"], "formule": f["formule"],
            "confidentialite": f["confidentialite"], "donnee_personnelle": f["donnee_personnelle"], "gxp": f["gxp"],
            "colonnes_liees": [f"{i} = {colonnes.get(i, 'inconnue')}" for i in liens],
        })

    consigne = f"""Tu es l'assistant du Data Governance Leader d'un laboratoire pharmaceutique.
Ces fiches du domaine {domaine} sont critiques (GxP, donnée personnelle ou confidentialité Restreint).
Le domaine est en standard bis : le Data Manager rédige et valide seul, tu es le garde-fou.
Analyse chaque dossier :
- la classification est-elle justifiée (GxP, donnée personnelle, confidentialité) ?
- la définition respecte-t-elle le standard : {regles["regle_definition"]}
- les colonnes liées représentent-elles réellement l'élément (une colonne d'un autre Business Object est une erreur) ?
- pour un KPI, la formule est-elle cohérente ?
Sois exigeant mais juste.

Dossiers : {json.dumps(dossiers, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, conforme (true ou false), motif (chaîne vide si conforme, sinon explication courte et actionnable), analyse (une phrase pour le Leader humain)."""

    print(f"{AGENT} : analyse de {len(fiches)} dossier(s) critique(s) du domaine {domaine}…")
    for a in demander_gemini(consigne):
        fiche = next(f for f in fiches if f["id"] == a["id"])
        if a.get("conforme") is False:
            nb = (fiche["nb_rejets"] or 0) + 1
            bloque = nb > regles["max_allers_retours"]
            mettre_a_jour(a["id"], AGENT, "Confirmation : non conforme", {
                "statut": "Bloqué" if bloque else "À corriger",
                "acteur_suivant": "Data Governance Leader (humain)" if bloque else "AG-BIS-MANAGER",
                "nb_rejets": nb,
                "motif_rejet": a.get("motif", ""),
            }, detail=a.get("motif", ""))
        else:
            mettre_a_jour(a["id"], AGENT, "Confirmation : analyse conforme", {
                "acteur_suivant": "Data Governance Leader (humain)",
                "commentaire_ia": (fiche["commentaire_ia"] or "") + " | Analyse Leader IA : conforme. " + a.get("analyse", ""),
            }, detail=a.get("analyse", ""))
    print(f"{AGENT} : analyses terminées, confirmation finale au Data Governance Leader humain.")