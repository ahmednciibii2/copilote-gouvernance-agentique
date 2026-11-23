import json

from outils import demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-GRP-OWNER"


def preparer_decision(domaine):
    """Prépare le dossier de décision du Data Owner humain (standard groupe). Ne décide jamais."""
    infos = infos_domaine(domaine)
    if infos["standard"] != "groupe":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard groupe, rien à faire.")
        return

    owner = infos["data_owner"]
    fiches = [f for f in lire_fiches(domaine=domaine, statut="À valider") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucune fiche en attente de dossier pour {domaine}.")
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
            "commentaires_precedents": f["commentaire_ia"],
        })

    consigne = f"""Tu es l'assistant de {owner}, Data Owner du domaine {domaine} dans un laboratoire pharmaceutique.
Tu prépares sa décision de certification ; c'est lui qui décide, pas toi.
Pour chaque fiche, rédige :
- synthese : une phrase qui résume la fiche pour un décideur métier ;
- recommandation : "Valider" ou "À corriger" ;
- motif : si "À corriger", la raison en une phrase ; sinon chaîne vide ;
- points_attention : ce que le Data Owner doit avoir en tête (criticité GxP, donnée personnelle, absence de colonne dans le SI…), ou chaîne vide.

Fiches : {json.dumps(dossiers, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, synthese, recommandation, motif, points_attention."""

    print(f"{AGENT} : préparation de {len(fiches)} dossier(s) de décision pour {owner}…")
    for d in demander_gemini(consigne):
        fiche = next(f for f in fiches if f["id"] == d["id"])
        texte = f' | Dossier Owner IA : {d.get("recommandation", "")}. {d.get("synthese", "")}'
        if d.get("motif"):
            texte += f' Motif proposé : {d["motif"]}'
        if d.get("points_attention"):
            texte += f' Points d\'attention : {d["points_attention"]}'
        mettre_a_jour(d["id"], AGENT, "Dossier de décision préparé", {
            "acteur_suivant": f"Data Owner : {owner} (humain)",
            "commentaire_ia": (fiche["commentaire_ia"] or "") + texte,
        }, detail=d.get("recommandation", ""))
    print(f"{AGENT} : dossiers prêts, décision à {owner}.")