import json

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-BIS-LEADER"


def confirmer(domaine):
    """Analyse les dossiers critiques du standard bis (glossaire et colonnes) ; la confirmation reste humaine."""
    infos = infos_domaine(domaine)
    if infos["standard"] != "bis":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard bis, rien à faire.")
        return

    regles = charger_regles()
    fiches = [f for f in lire_fiches(domaine=domaine, statut="En confirmation") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucun dossier critique à analyser pour {domaine}.")
        return
    par_id = {f["id"]: f for f in fiches}

    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    termes = {t["id"]: t["nom"] for t in lire_fiches(domaine=domaine, chemin="B")}
    dossiers = []
    for f in fiches:
        liens = [i.strip() for i in (f["colonnes_liees"] or "").split(",") if i.strip()]
        terme = f["terme_lie"] or ""
        dossiers.append({
            "id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
            "exemples": f["exemples"], "definition": f["definition"], "formule": f["formule"],
            "confidentialite": f["confidentialite"], "donnee_personnelle": f["donnee_personnelle"], "gxp": f["gxp"],
            "colonnes_liees": [f"{i} = {colonnes.get(i, 'inconnue')}" for i in liens],
            "terme_lie": f"{terme} = {termes[terme]}" if terme in termes else terme,
        })

    consigne = f"""Tu es l'assistant du Data Governance Leader d'un laboratoire pharmaceutique.
Ces fiches du domaine {domaine} sont critiques (GxP, donnée personnelle ou confidentialité Restreint).
Le domaine est en standard bis : le Data Manager rédige et valide seul, tu es le garde-fou.
Analyse chaque dossier :
- la classification est-elle justifiée ? GxP et confidentialité sont deux axes indépendants : une donnée GxP n'est pas forcément confidentielle ;
  "Restreint" est réservé aux données très sensibles (coordonnées bancaires, données personnelles sensibles, secrets industriels) ;
- terme du glossaire : définition conforme ({regles["regle_definition"]}), colonnes liées qui représentent réellement l'élément, formule cohérente pour un KPI ;
- colonne technique : terme_lie correspond-il au sens réel de la colonne (voir ses exemples) ?
  La forme « NOUVEAU : nom du terme (Business Object) » est la forme normale d'un nouveau terme proposé : ne la considère pas comme une erreur ;
  vérifie seulement que le nouveau terme et sa définition sont pertinents.
Sois exigeant mais juste.

Dossiers : {json.dumps(dossiers, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, conforme (true ou false), motif (chaîne vide si conforme, sinon explication courte et actionnable), analyse (une phrase pour le Leader humain)."""

    print(f"{AGENT} : analyse de {len(fiches)} dossier(s) critique(s) du domaine {domaine}…")
    for a in demander_gemini(consigne):
        fiche = par_id.get(a.get("id")) if isinstance(a, dict) else None
        if fiche is None:
            continue
        if a.get("conforme") is False:
            nb = (fiche["nb_rejets"] or 0) + 1
            bloque = nb > regles["max_allers_retours"]
            mettre_a_jour(fiche["id"], AGENT, "Confirmation : non conforme", {
                "statut": "Bloqué" if bloque else "À corriger",
                "acteur_suivant": "Data Governance Leader (humain)" if bloque else "AG-BIS-MANAGER",
                "nb_rejets": nb,
                "motif_rejet": a.get("motif", ""),
            }, detail=a.get("motif", ""))
        else:
            ecart = ""
            if fiche["type"] == "Colonne technique" and (fiche["terme_lie"] or "").startswith("NOUVEAU"):
                ecart = " Écart A→B : nouveau terme métier à arbitrer."
            mettre_a_jour(fiche["id"], AGENT, "Confirmation : analyse conforme", {
                "acteur_suivant": "Data Governance Leader (humain)",
                "commentaire_ia": (fiche["commentaire_ia"] or "") + " | Analyse Leader IA : conforme. " + a.get("analyse", "") + ecart,
            }, detail=a.get("analyse", ""))
    print(f"{AGENT} : analyses terminées, confirmation finale au Data Governance Leader humain.")