"""AG-GRP-LEADER — agent contrôleur du standard groupe (assiste le Data Governance Leader).

Contrôle chaque fiche « À valider » avec la grille C1 à C7 de la charte, point par point :
- par le code : C1 (champs obligatoires), C3 (valeurs autorisées), C6 (écarts), C7 (criticité) ;
- par Gemini : C2 (définition), C3 (cohérence), C4 (colonnes liées), C5 (formule).
Puis : relais à l'agent Owner, retour au Steward, ou blocage au-delà de max_allers_retours.
"""
import json

from commun.outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "groupe"
AGENT = "AG-GRP-LEADER"
utiliser_standard(STANDARD)   # cet agent ne travaille que dans le standard groupe

POINTS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
SYMBOLE = {"ok": "✅", "ko": "❌", "alerte": "⚠️", "na": "–"}


def est_critique(f):
    """C7 : règle de criticité de la charte (calculée par le code, pas par l'IA)."""
    return f["reglementee"] == "Oui" or f["donnee_personnelle"] == "Oui" or f["confidentialite"] == "Restreint"


def controle_code(f, regles):
    """Contrôles sans IA : C1, valeurs de C3, C6 et C7. Renvoie {point: (resultat, motif)}."""
    r = {}

    # C1 : champs obligatoires selon le type de fiche
    absents = []
    for champ in regles["champs_obligatoires"].get(f["type"], []):
        if champ == "classification":
            if not (f["confidentialite"] and f["donnee_personnelle"] and f["reglementee"]):
                absents.append("classification")
        elif champ == "colonnes_liees":
            continue   # un manque dans le SI n'est pas une faute du rédacteur : traité en C6
        elif not f[champ]:
            absents.append(champ)
    r["C1"] = ("ko", "Champs obligatoires manquants : " + ", ".join(absents)) if absents else ("ok", "")

    # C3 (partie code) : valeurs autorisées par la charte
    cl = regles["classification"]
    hors = [nom for nom in ("confidentialite", "donnee_personnelle", "reglementee") if f[nom] and f[nom] not in cl[nom]]
    r["C3_valeurs"] = ("ko", "Valeurs hors charte : " + ", ".join(hors)) if hors else ("ok", "")

    # C6 : écarts entre glossaire et SI (signalés, jamais refusés)
    if f["type"] in ("Business Term", "KPI") and not f["colonnes_liees"]:
        r["C6"] = ("alerte", "Écart B→A : aucune colonne correspondante dans le SI.")
    elif f["type"] == "Colonne technique" and (f["terme_lie"] or "").startswith("NOUVEAU"):
        r["C6"] = ("alerte", "Écart A→B : nouveau terme métier à arbitrer.")
    else:
        r["C6"] = ("ok", "")

    # C7 : criticité (information pour le Data Owner, jamais refusée)
    r["C7"] = ("alerte", "Fiche critique (réglementée, personnelle ou Restreint).") if est_critique(f) else ("ok", "")
    return r


def controler(domaine):
    """Contrôle les fiches soumises (glossaire et colonnes techniques) et fait le relais (standard groupe)."""
    infos_domaine(domaine)   # erreur claire si le domaine n'est pas dans le registre du groupe
    regles = charger_regles()
    grille = regles["grille_controle"]
    fiches = [f for f in lire_fiches(domaine=domaine, statut="À valider") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucune fiche à contrôler pour {domaine}.")
        return
    par_id = {f["id"]: f for f in fiches}

    # Contrôle par Gemini : C2, C3 (cohérence), C4, C5
    colonnes = {c["id"]: c["nom"] for c in lire_fiches(domaine=domaine, chemin="A")}
    termes = {t["id"]: t["nom"] for t in lire_fiches(domaine=domaine, chemin="B")}
    a_controler = []
    for f in fiches:
        liens = [i.strip() for i in (f["colonnes_liees"] or "").split(",") if i.strip()]
        terme = f["terme_lie"] or ""
        a_controler.append({
            "id": f["id"], "type": f["type"], "nom": f["nom"], "business_object": f["business_object"],
            "exemples": f["exemples"], "definition": f["definition"], "formule": f["formule"],
            "confidentialite": f["confidentialite"], "donnee_personnelle": f["donnee_personnelle"], "reglementee": f["reglementee"],
            "colonnes_liees": [f"{i} = {colonnes.get(i, 'inconnue')}" for i in liens],
            "terme_lie": f"{terme} = {termes[terme]}" if terme in termes else terme,
        })

    consigne = f"""Tu es l'assistant du Data Governance Leader d'une entreprise (standard groupe).
Contrôle ces fiches du catalogue du domaine {domaine} avec la grille de la charte, point par point :
- C2 : {grille["C2"]}. Règle : {regles["regle_definition"]}
  Pour une colonne technique, la définition n'est exigée que pour un NOUVEAU terme proposé ; sinon réponds "na".
- C3 : {grille["C3"]}. Confidentialité, donnée personnelle et donnée réglementée sont trois axes indépendants.
  Donnée réglementée : {regles["definition_reglementee"]}
  "Restreint" est réservé aux données très sensibles (coordonnées bancaires, données personnelles sensibles, secrets d'affaires).
- C4 : {grille["C4"]}. Une colonne d'un autre Business Object est une erreur. "na" si aucune colonne liée.
  Pour une colonne technique : terme_lie doit correspondre au sens réel de la colonne (voir ses exemples).
  La forme « NOUVEAU : nom du terme (Business Object) » est normale : vérifie seulement que le terme proposé est pertinent.
- C5 : {grille["C5"]}. "na" si l'élément n'est pas un KPI.
Sois exigeant mais juste : "ko" seulement pour une vraie erreur.

Fiches : {json.dumps(a_controler, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, C2, C3, C4, C5.
Chaque point est un objet {{"resultat": "ok" ou "ko" ou "na", "motif": "chaîne vide si ok ou na, sinon explication courte et actionnable pour le rédacteur"}}."""

    print(f"{AGENT} : contrôle de {len(fiches)} fiche(s) du domaine {domaine} (grille C1 à C7)…")
    avis = {a.get("id"): a for a in demander_gemini(consigne) if isinstance(a, dict)}

    # Fusion des résultats, puis tâche de frontière : relais à l'Owner, retour au Steward, ou blocage
    for f in fiches:
        r = controle_code(f, regles)
        a = avis.get(f["id"], {})
        for point in ("C2", "C3", "C4", "C5"):
            v = a.get(point) if isinstance(a.get(point), dict) else {}
            resultat = v.get("resultat", "na") if v.get("resultat") in ("ok", "ko", "na") else "na"
            r[point] = (resultat, v.get("motif", ""))
        if r["C3_valeurs"][0] == "ko":   # le contrôle des valeurs par le code l'emporte
            r["C3"] = ("ko", " ; ".join(m for m in (r["C3_valeurs"][1], r["C3"][1]) if m))
        del r["C3_valeurs"]

        ligne_grille = " | ".join(f"{p} {SYMBOLE[r[p][0]]}" for p in POINTS)
        motifs = [f"{p} : {r[p][1]}" for p in POINTS[:5] if r[p][0] == "ko"]
        alertes = [r[p][1] for p in ("C6", "C7") if r[p][0] == "alerte"]

        if motifs:
            nb = (f["nb_rejets"] or 0) + 1
            bloque = nb > regles["max_allers_retours"]
            mettre_a_jour(f["id"], AGENT, "Contrôle grille C1-C7 : non conforme", {
                "statut": "Bloqué" if bloque else "À corriger",
                "acteur_suivant": "Data Governance Leader (humain)" if bloque else "AG-GRP-STEWARD",
                "nb_rejets": nb,
                "motif_rejet": " ; ".join(motifs),
            }, detail=ligne_grille + " — " + " ; ".join(motifs))
        else:
            mettre_a_jour(f["id"], AGENT, "Contrôle grille C1-C7 : complet", {
                "acteur_suivant": "AG-GRP-OWNER",
                "commentaire_ia": (par_id[f["id"]]["commentaire_ia"] or "") + " | Contrôle Leader : " + ligne_grille
                                  + ("" if not alertes else " — " + " ".join(alertes)),
            }, detail=ligne_grille + ("" if not alertes else " — " + " ".join(alertes)))

    nb_ok = sum(1 for f in lire_fiches(domaine=domaine) if f["acteur_suivant"] == "AG-GRP-OWNER")
    print(f"{AGENT} : contrôle terminé, {nb_ok} fiche(s) transmise(s) à AG-GRP-OWNER.")