"""AG-BIS-MANAGER — agent du Data Manager, standard bis (le Data Manager cumule Owner et Steward).

Deux tâches, comme son humain :
1. documenter_business_object : rédige la définition (et la formule d'un KPI) des fiches du glossaire ;
2. preparer_decision : prépare le dossier de décision des termes NON critiques pour le Data Manager
   (les colonnes techniques ont leur propre dossier, préparé par l'agent Custodian).
Ne fait ni les liens avec les colonnes (croisements), ni la classification (agent DPO).
Circuit : Manager (rédaction) → Croisement B→A → Agent DPO → [critique : Leader bis → Data Governance Leader humain]
          → Manager (dossier, non critique) → Data Manager humain.
"""
import json

from commun.outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "bis"
AGENT = "AG-BIS-MANAGER"
SUIVANT = "AG-BIS-CROISEMENT-BA"
utiliser_standard(STANDARD)   # cet agent ne travaille que dans le standard bis


def documenter_business_object(domaine, business_object):
    """Rédige les fiches d'un Business Object (nouvelles ou à corriger), puis relais au croisement B→A."""
    acteurs = infos_domaine(domaine)   # erreur claire si le domaine n'est pas dans le registre du bis
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

    consigne = f"""Tu es l'assistant du Data Manager ({acteurs["data_manager"]}) du domaine {domaine} dans une entreprise.
Tu rédiges les fiches du Business Object « {business_object} » du glossaire métier.

Règles de la charte du standard bis :
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


def points_attention_code(fiche):
    """Points d'attention calculés par le code : ils figurent toujours dans le dossier."""
    points = []
    if fiche["type"] in ("Business Term", "KPI") and not fiche["colonnes_liees"]:
        points.append("Écart B→A : aucune colonne correspondante dans le SI.")
    if fiche["type"] == "Colonne technique" and (fiche["terme_lie"] or "").startswith("NOUVEAU"):
        points.append("Écart A→B : nouveau terme métier à arbitrer.")
    if "écart d'héritage" in (fiche.get("heritage") or ""):
        points.append("Écart d'héritage : la colonne paraît plus sensible que son terme, niveau le plus strict conservé.")
    if fiche["nb_rejets"]:
        points.append(f"Déjà refusée {fiche['nb_rejets']} fois par le contrôle (dernier motif : {fiche['motif_rejet'] or 'non précisé'}).")
    return points


def construire_dossier(fiche, ia):
    """Assemble le dossier de décision à partir de la fiche et de la réponse de Gemini (ia)."""
    points = points_attention_code(fiche)
    if ia.get("points_attention"):
        points.append(ia["points_attention"])
    return (
        f" | Dossier de décision — Synthèse : {ia.get('synthese', '')}"
        f" · Recommandation : {ia.get('recommandation', '')}"
        f" · Motif : {ia.get('motif') or '—'}"
        f" · Points d'attention : {' '.join(points) if points else 'aucun'}"
        " · Contrôle C1-C7 : non requis (fiche non critique)"
    )


def preparer_decision(domaine):
    """Prépare le dossier de décision du Data Manager humain pour les fiches non critiques (standard bis). Ne décide jamais."""
    manager = infos_domaine(domaine)["data_manager"]
    fiches = [f for f in lire_fiches(domaine=domaine, statut="À valider") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucune fiche en attente de dossier pour {domaine}.")
        return

    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    a_preparer = []
    for f in fiches:
        liens = [i.strip() for i in (f["colonnes_liees"] or "").split(",") if i.strip()]
        a_preparer.append({
            "id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
            "definition": f["definition"], "formule": f["formule"],
            "confidentialite": f["confidentialite"], "donnee_personnelle": f["donnee_personnelle"], "reglementee": f["reglementee"],
            "colonnes_liees": [f"{i} = {colonnes.get(i, 'inconnue')}" for i in liens],
            "points_deja_identifies": points_attention_code(f),
        })

    consigne = f"""Tu es l'assistant de {manager}, Data Manager du domaine {domaine} dans une entreprise (standard bis).
Tu prépares sa décision de certification ; c'est lui qui décide, pas toi.
Pour chaque fiche, rédige :
- synthese : une phrase qui résume la fiche pour un décideur métier ;
- recommandation : "Valider" ou "À corriger" ;
- motif : si "À corriger", la raison en une phrase ; sinon chaîne vide ;
- points_attention : un point utile au Data Manager qui ne figure pas déjà dans points_deja_identifies, ou chaîne vide.

Fiches : {json.dumps(a_preparer, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, synthese, recommandation, motif, points_attention."""

    print(f"{AGENT} : préparation de {len(fiches)} dossier(s) de décision pour {manager}…")
    reponses = {d.get("id"): d for d in demander_gemini(consigne) if isinstance(d, dict)}

    prets = 0
    for f in fiches:
        ia = reponses.get(f["id"])
        if ia is None:
            print(f"  {f['id']} : pas de réponse de Gemini, la fiche reste en attente (relancer plus tard).")
            continue
        mettre_a_jour(f["id"], AGENT, "Dossier de décision préparé", {
            "acteur_suivant": f"Data Manager : {manager} (humain)",
            "commentaire_ia": (f["commentaire_ia"] or "") + construire_dossier(f, ia),
        }, detail=ia.get("recommandation", ""))
        prets += 1
    print(f"{AGENT} : {prets} dossier(s) prêt(s), décision à {manager}.")
