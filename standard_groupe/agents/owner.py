"""AG-GRP-OWNER — agent préparateur de décision du standard groupe (assiste le Data Owner).

Pour chaque fiche jugée complète par l'agent Leader, prépare un dossier de décision en 5 rubriques :
Synthèse · Recommandation · Motif · Points d'attention · Contrôle C1-C7.
Il ne décide jamais : la fiche attend ensuite le Data Owner humain du domaine.
"""
import json
import re

from commun.outils import demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard
from standard_groupe.agents.leader import est_critique

STANDARD = "groupe"
AGENT = "AG-GRP-OWNER"
utiliser_standard(STANDARD)   # cet agent ne travaille que dans le standard groupe


def grille_du_leader(fiche):
    """Retrouve la ligne de grille écrite par l'agent Leader (ex. « C1 ✅ | … | C7 ⚠️ »)."""
    trouve = re.search(r"Contrôle Leader : (C1 .*?C7 \S+)", fiche["commentaire_ia"] or "")
    return trouve.group(1) if trouve else "non disponible"


def points_attention_code(fiche):
    """Points d'attention calculés par le code : ils figurent toujours dans le dossier."""
    points = []
    if est_critique(fiche):
        raisons = [r for r, ok in (("donnée réglementée", fiche["reglementee"] == "Oui"),
                                   ("donnée personnelle", fiche["donnee_personnelle"] == "Oui"),
                                   ("classée Restreint", fiche["confidentialite"] == "Restreint")) if ok]
        points.append("Fiche critique : " + ", ".join(raisons) + ".")
    if fiche["type"] in ("Business Term", "KPI") and not fiche["colonnes_liees"]:
        points.append("Écart B→A : aucune colonne correspondante dans le SI.")
    if fiche["type"] == "Colonne technique" and (fiche["terme_lie"] or "").startswith("NOUVEAU"):
        points.append("Écart A→B : nouveau terme métier à arbitrer.")
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
        f" · Contrôle C1-C7 : {grille_du_leader(fiche)}"
    )


def preparer_decision(domaine):
    """Prépare le dossier de décision du Data Owner humain (standard groupe). Ne décide jamais."""
    owner = infos_domaine(domaine)["data_owner"]   # erreur claire si le domaine n'est pas dans le registre du groupe
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
            "controle_leader": grille_du_leader(f),
            "points_deja_identifies": points_attention_code(f),
        })

    consigne = f"""Tu es l'assistant de {owner}, Data Owner du domaine {domaine} dans une entreprise (standard groupe).
Tu prépares sa décision de certification ; c'est lui qui décide, pas toi.
Pour chaque fiche, rédige :
- synthese : une phrase qui résume la fiche pour un décideur métier ;
- recommandation : "Valider" ou "À corriger" ;
- motif : si "À corriger", la raison en une phrase ; sinon chaîne vide ;
- points_attention : un point utile au Data Owner qui ne figure pas déjà dans points_deja_identifies, ou chaîne vide.

Fiches : {json.dumps(a_preparer, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, synthese, recommandation, motif, points_attention."""

    print(f"{AGENT} : préparation de {len(fiches)} dossier(s) de décision pour {owner}…")
    reponses = {d.get("id"): d for d in demander_gemini(consigne) if isinstance(d, dict)}

    prets = 0
    for f in fiches:
        ia = reponses.get(f["id"])
        if ia is None:
            print(f"  {f['id']} : pas de réponse de Gemini, la fiche reste en attente (relancer plus tard).")
            continue
        mettre_a_jour(f["id"], AGENT, "Dossier de décision préparé", {
            "acteur_suivant": f"Data Owner : {owner} (humain)",
            "commentaire_ia": (f["commentaire_ia"] or "") + construire_dossier(f, ia),
        }, detail=ia.get("recommandation", ""))
        prets += 1
    print(f"{AGENT} : {prets} dossier(s) prêt(s), décision à {owner}.")
