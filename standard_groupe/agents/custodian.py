"""AG-GRP-CUSTODIAN — agent du Data Custodian, standard groupe (contrepartie technique du Data Steward).

Le Data Custodian possède le chemin A (métadonnées techniques). Deux tâches, comme son humain :
1. documenter_colonnes : description technique (rôle dans le modèle, format observé), lignage
   (système › table › colonne) et règle qualité proposée, pour chaque colonne nouvelle ou à corriger ;
2. preparer_decision : dossier de décision des colonnes pour le Data Custodian humain.
Circuit d'une colonne : Custodian (documentation) → Croisement A→B → Agent DPO → Leader (C1-C7)
                         → Custodian (dossier) → Data Custodian humain.
Plus tard (chantier B), c'est cet agent qui recevra les colonnes issues du scan de bases et d'APIs.
"""
import json
import re

from commun.outils import demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "groupe"
AGENT = "AG-GRP-CUSTODIAN"
SUIVANT = "AG-GRP-CROISEMENT-AB"
METIER = "Data Owner"   # décideur métier, pour un terme NOUVEAU à créer
utiliser_standard(STANDARD)   # cet agent ne travaille que dans le standard groupe


def lignage(colonne):
    """Lignage technique minimal, calculé par le code : système › table › colonne."""
    return f"{colonne['systeme']} › {colonne['table_source']} › {colonne['colonne']}"


def documenter_colonnes(domaine):
    """Documente techniquement les colonnes nouvelles ou à corriger, puis relais au croisement A→B."""
    acteurs = infos_domaine(domaine)   # erreur claire si le domaine n'est pas dans le registre
    colonnes = [c for c in lire_fiches(domaine=domaine, chemin="A") if c["statut"] in ("Identifié", "À corriger")]
    if not colonnes:
        print(f"{AGENT} : aucune colonne à documenter pour {domaine}.")
        return

    a_documenter = [{"id": c["id"], "systeme": c["systeme"], "table": c["table_source"], "colonne": c["colonne"],
                     "exemples": c["exemples"], "description_precedente": c["description_technique"] or "",
                     "regle_precedente": c["regle_qualite"] or "", "motif_rejet": c["motif_rejet"] or ""} for c in colonnes]

    consigne = f"""Tu es l'assistant du Data Custodian ({acteurs["data_custodian"]}) du domaine {domaine} dans une entreprise.
Le Data Custodian est le responsable technique des données : il documente les sources, les flux et les modèles,
et met en place les contrôles qualité. Pour chaque colonne technique ci-dessous, rédige :
- description_technique : une ou deux phrases techniques : rôle de la colonne dans le modèle (identifiant, clé, date,
  montant, quantité, code, statut, libellé…), format observé d'après les exemples, unité si pertinente ;
- regle_qualite : une règle de contrôle qualité vérifiable et précise (ex. « non nulle, format L####-#### »,
  « date ≥ date de fabrication », « valeur dans la liste LIBERE, BLOQUE, EN_ATTENTE », « montant ≥ 0 ») ;
- Si un motif_rejet est fourni, corrige ta proposition précédente en conséquence.
N'invente pas de signification métier : le rattachement au glossaire est fait ensuite par un autre agent.

Colonnes : {json.dumps(a_documenter, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, description_technique, regle_qualite, justification."""

    print(f"{AGENT} : documentation technique de {len(colonnes)} colonne(s) du domaine {domaine}…")
    propositions = {p.get("id"): p for p in demander_gemini(consigne) if isinstance(p, dict)}

    for c in colonnes:
        p = propositions.get(c["id"])
        if p is None:
            print(f"  {c['id']} : pas de réponse de Gemini, la colonne reste en attente.")
            continue
        mettre_a_jour(c["id"], AGENT, "Documentation technique proposée", {
            "description_technique": p.get("description_technique", ""),
            "regle_qualite": p.get("regle_qualite", ""),
            "lignage": lignage(c),
            "statut": "En rédaction",
            "acteur_suivant": SUIVANT,
            "commentaire_ia": "Documentation technique proposée par IA (Custodian). " + p.get("justification", ""),
        }, detail=p.get("justification", ""))
    print(f"{AGENT} : documentation terminée, relais à {SUIVANT}.")


def grille_du_leader(fiche):
    """Retrouve la ligne de grille écrite par l'agent Leader (ex. « C1 ✅ | … | C7 ⚠️ »)."""
    trouve = re.search(r"Contrôle Leader : (C1 .*?C7 \S+)", fiche["commentaire_ia"] or "")
    return trouve.group(1) if trouve else "non requis (fiche non critique)"


def points_attention_code(colonne):
    """Points d'attention calculés par le code : ils figurent toujours dans le dossier."""
    points = []
    if colonne["critique"] == "Oui":
        raisons = [r for r, ok in (("donnée réglementée", colonne["reglementee"] == "Oui"),
                                   ("donnée personnelle", colonne["donnee_personnelle"] == "Oui"),
                                   ("classée Restreint", colonne["confidentialite"] == "Restreint")) if ok]
        points.append("Colonne critique : " + ", ".join(raisons) + ".")
    if (colonne["terme_lie"] or "").startswith("NOUVEAU"):
        points.append(f"Écart A→B : terme métier à créer ({colonne['terme_lie']}) ; sa création relève du {METIER}.")
    if "écart d'héritage" in (colonne.get("heritage") or ""):
        points.append("Écart d'héritage : la colonne paraît plus sensible que son terme, niveau le plus strict conservé.")
    if colonne["nb_rejets"]:
        points.append(f"Déjà refusée {colonne['nb_rejets']} fois (dernier motif : {colonne['motif_rejet'] or 'non précisé'}).")
    return points


def construire_dossier(colonne, ia):
    """Assemble le dossier de décision d'une colonne à partir de la fiche et de la réponse de Gemini (ia)."""
    points = points_attention_code(colonne)
    if ia.get("points_attention"):
        points.append(ia["points_attention"])
    return (
        f" | Dossier de décision — Synthèse : {ia.get('synthese', '')}"
        f" · Recommandation : {ia.get('recommandation', '')}"
        f" · Motif : {ia.get('motif') or '—'}"
        f" · Points d'attention : {' '.join(points) if points else 'aucun'}"
        f" · Contrôle C1-C7 : {grille_du_leader(colonne)}"
    )


def preparer_decision(domaine):
    """Prépare le dossier de décision du Data Custodian humain pour les colonnes. Ne décide jamais."""
    custodian = infos_domaine(domaine)["data_custodian"]
    colonnes = [c for c in lire_fiches(domaine=domaine, chemin="A", statut="À valider") if c["acteur_suivant"] == AGENT]
    if not colonnes:
        print(f"{AGENT} : aucune colonne en attente de dossier pour {domaine}.")
        return

    a_preparer = [{"id": c["id"], "colonne": c["nom"], "lignage": c["lignage"], "exemples": c["exemples"],
                   "description_technique": c["description_technique"], "regle_qualite": c["regle_qualite"],
                   "terme_lie": c["terme_lie"], "confidentialite": c["confidentialite"],
                   "donnee_personnelle": c["donnee_personnelle"], "reglementee": c["reglementee"],
                   "points_deja_identifies": points_attention_code(c)} for c in colonnes]

    consigne = f"""Tu es l'assistant de {custodian}, Data Custodian du domaine {domaine} dans une entreprise (standard {STANDARD}).
Tu prépares sa décision sur la documentation technique de ces colonnes ; c'est lui qui décide, pas toi.
Pour chaque colonne, rédige :
- synthese : une phrase qui résume la colonne (rôle, source, rattachement) pour un responsable technique ;
- recommandation : "Valider" ou "À corriger" ;
- motif : si "À corriger", la raison en une phrase ; sinon chaîne vide ;
- points_attention : un point utile au Data Custodian (règle qualité à outiller, risque technique…) qui ne figure
  pas déjà dans points_deja_identifies, ou chaîne vide.

Colonnes : {json.dumps(a_preparer, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, synthese, recommandation, motif, points_attention."""

    print(f"{AGENT} : préparation de {len(colonnes)} dossier(s) de décision pour {custodian}…")
    reponses = {d.get("id"): d for d in demander_gemini(consigne) if isinstance(d, dict)}

    prets = 0
    for c in colonnes:
        ia = reponses.get(c["id"])
        if ia is None:
            print(f"  {c['id']} : pas de réponse de Gemini, la colonne reste en attente (relancer plus tard).")
            continue
        mettre_a_jour(c["id"], AGENT, "Dossier de décision préparé", {
            "acteur_suivant": f"Data Custodian : {custodian} (humain)",
            "commentaire_ia": (c["commentaire_ia"] or "") + construire_dossier(c, ia),
        }, detail=ia.get("recommandation", ""))
        prets += 1
    print(f"{AGENT} : {prets} dossier(s) prêt(s), décision à {custodian}.")
