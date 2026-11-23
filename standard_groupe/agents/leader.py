import json

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour

AGENT = "AG-GRP-LEADER"


def controler(domaine):
    """Contrôle les fiches soumises (glossaire et colonnes techniques) et fait le relais (standard groupe)."""
    if infos_domaine(domaine)["standard"] != "groupe":
        print(f"{AGENT} : le domaine {domaine} n'est pas en standard groupe, rien à faire.")
        return

    regles = charger_regles()
    fiches = [f for f in lire_fiches(domaine=domaine, statut="À valider") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucune fiche à contrôler pour {domaine}.")
        return
    par_id = {f["id"]: f for f in fiches}

    # 1. Contrôle automatique des champs obligatoires (sans IA)
    manquants = {}
    for f in fiches:
        absents = []
        for champ in regles["champs_obligatoires"].get(f["type"], []):
            if champ == "classification":
                if not (f["confidentialite"] and f["donnee_personnelle"] and f["gxp"]):
                    absents.append("classification")
            elif champ == "colonnes_liees":
                continue  # un manque dans le SI n'est pas une faute du rédacteur : signalé plus bas
            elif not f[champ]:
                absents.append(champ)
        manquants[f["id"]] = absents

    # 2. Contrôle de cohérence par Gemini
    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    termes = {t["id"]: t["nom"] for t in lire_fiches(domaine=domaine, chemin="B")}
    a_controler = []
    for f in fiches:
        liens = [i.strip() for i in (f["colonnes_liees"] or "").split(",") if i.strip()]
        terme = f["terme_lie"] or ""
        a_controler.append({
            "id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
            "exemples": f["exemples"], "definition": f["definition"], "formule": f["formule"],
            "confidentialite": f["confidentialite"], "donnee_personnelle": f["donnee_personnelle"], "gxp": f["gxp"],
            "colonnes_liees": [f"{i} = {colonnes.get(i, 'inconnue')}" for i in liens],
            "terme_lie": f"{terme} = {termes[terme]}" if terme in termes else terme,
        })

    consigne = f"""Tu es l'assistant du Data Governance Leader d'un laboratoire pharmaceutique.
Contrôle la qualité de ces fiches du catalogue du domaine {domaine}, par rapport au standard :
- Terme du glossaire (Business Object, Business Term, KPI) : définition conforme ({regles["regle_definition"]}),
  classification cohérente, colonnes liées qui représentent réellement l'élément (une colonne d'un autre Business Object est une erreur),
  formule cohérente pour un KPI.
- Colonne technique : terme_lie doit correspondre au sens réel de la colonne (voir ses exemples).
  La forme « NOUVEAU : nom du terme (Business Object) » est la forme normale d'un nouveau terme proposé : ne la considère pas comme une erreur.
  Vérifie seulement que le nouveau terme et sa définition sont pertinents. La définition n'est exigée que pour un nouveau terme.
- GxP = "Oui" si l'élément sert à garantir la qualité, la traçabilité ou la sécurité du médicament.
- GxP et confidentialité sont deux axes indépendants : une donnée GxP n'est pas forcément confidentielle.
  "Restreint" est réservé aux données très sensibles (coordonnées bancaires, données personnelles sensibles, secrets industriels).
Sois exigeant mais juste : ne rejette que pour une vraie erreur.

Fiches : {json.dumps(a_controler, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, conforme (true ou false), motif (chaîne vide si conforme, sinon explication courte et actionnable pour le rédacteur)."""

    print(f"{AGENT} : contrôle de {len(fiches)} fiche(s) du domaine {domaine}…")
    avis = {a.get("id"): a for a in demander_gemini(consigne) if isinstance(a, dict)}

    # 3. Tâche de frontière : relais à l'Owner, retour au rédacteur, ou blocage
    for f in fiches:
        motifs = []
        if manquants[f["id"]]:
            motifs.append("Champs obligatoires manquants : " + ", ".join(manquants[f["id"]]))
        if avis.get(f["id"], {}).get("conforme") is False:
            motifs.append(avis[f["id"]].get("motif", ""))

        if motifs:
            nb = (f["nb_rejets"] or 0) + 1
            bloque = nb > regles["max_allers_retours"]
            mettre_a_jour(f["id"], AGENT, "Contrôle du standard : non conforme", {
                "statut": "Bloqué" if bloque else "À corriger",
                "acteur_suivant": "Data Governance Leader (humain)" if bloque else "AG-GRP-STEWARD",
                "nb_rejets": nb,
                "motif_rejet": " ; ".join(motifs),
            }, detail=" ; ".join(motifs))
        else:
            ecart = ""
            if f["type"] in ("Business Term", "KPI") and not f["colonnes_liees"]:
                ecart = " Écart B→A : aucune colonne correspondante dans le SI."
            if f["type"] == "Colonne technique" and (f["terme_lie"] or "").startswith("NOUVEAU"):
                ecart = " Écart A→B : nouveau terme métier à arbitrer."
            mettre_a_jour(f["id"], AGENT, "Contrôle du standard : complet", {
                "acteur_suivant": "AG-GRP-OWNER",
                "commentaire_ia": (par_id[f["id"]]["commentaire_ia"] or "") + " | Contrôle Leader : complet." + ecart,
            })

    nb_ok = sum(1 for f in lire_fiches(domaine=domaine) if f["acteur_suivant"] == "AG-GRP-OWNER")
    print(f"{AGENT} : contrôle terminé, {nb_ok} fiche(s) transmise(s) à AG-GRP-OWNER.")