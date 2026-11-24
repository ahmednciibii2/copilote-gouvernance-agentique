"""AG-GRP-DPO — agent de classification du standard groupe (assiste le DPO et la conformité).

Classifie toutes les métadonnées, métier (termes, KPI) comme techniques (colonnes) :
confidentialité, donnée personnelle, donnée réglementée.
Règle d'héritage (charte, regle_heritage) :
- le terme métier porte la classification ;
- une colonne liée à un terme hérite de sa classification (calcul par le code) ;
- garde-fou : si la colonne paraît plus sensible que son terme, on garde le niveau le plus strict
  et un écart d'héritage est signalé au décideur ;
- une colonne sans terme (NOUVEAU) est classifiée directement.
Puis la criticité est calculée et la fiche passe « À valider » chez l'agent Leader.
"""
import json

from commun.outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "groupe"
AGENT = "AG-GRP-DPO"
SUIVANT = "AG-GRP-LEADER"
utiliser_standard(STANDARD)

AXES = ("confidentialite", "donnee_personnelle", "reglementee")


def valeurs_valides(classe, regles):
    """Ne garde que les valeurs autorisées par la charte (une valeur hors charte est laissée vide)."""
    return {axe: (classe.get(axe) if classe.get(axe) in regles["classification"][axe] else "") for axe in AXES}


def plus_strict(a, b, regles):
    """Valeur la plus stricte des deux sur un axe (ordre de la charte : la dernière valeur est la plus stricte)."""
    ordre = regles["classification"]
    resultat = {}
    for axe in AXES:
        rangs = [ordre[axe].index(v) for v in (a.get(axe), b.get(axe)) if v in ordre[axe]]
        resultat[axe] = ordre[axe][max(rangs)] if rangs else ""
    return resultat


def est_critique(classe):
    """Règle de criticité de la charte : réglementée, personnelle ou Restreint."""
    return classe.get("reglementee") == "Oui" or classe.get("donnee_personnelle") == "Oui" or classe.get("confidentialite") == "Restreint"


def classer_colonne(classe_colonne, classe_terme, id_terme, regles):
    """Applique l'héritage à une colonne. Renvoie (classification finale, texte d'héritage, écarts)."""
    if not id_terme or not any(classe_terme.get(a) for a in AXES):
        return classe_colonne, "directe (aucun terme classifié)", []
    finale = plus_strict(classe_colonne, classe_terme, regles)
    ecarts = [f"{axe} : terme {classe_terme.get(axe) or '?'} / colonne {classe_colonne.get(axe)}"
              for axe in AXES if finale[axe] != classe_terme.get(axe)]
    texte = f"héritée de {id_terme}" + (" (écart d'héritage : niveau le plus strict conservé)" if ecarts else "")
    return finale, texte, ecarts


def terme_parent(colonne, termes):
    """Terme dont la colonne hérite : son terme_lie (A→B), sinon un terme qui la liste dans colonnes_liees (B→A)."""
    if colonne["terme_lie"] in termes:
        return colonne["terme_lie"]
    for t in termes.values():
        if colonne["id"] in [i.strip() for i in (t["colonnes_liees"] or "").split(",")]:
            return t["id"]
    return ""


def classifier(domaine):
    """Classifie les fiches en attente (termes puis colonnes, avec héritage), puis relais à l'agent Leader."""
    infos_domaine(domaine)
    regles = charger_regles()
    fiches = [f for f in lire_fiches(domaine=domaine, statut="En rédaction") if f["acteur_suivant"] == AGENT]
    if not fiches:
        print(f"{AGENT} : aucune fiche à classifier pour {domaine}.")
        return

    a_classer = [{"id": f["id"], "chemin": "glossaire" if f["chemin"] == "B" else "colonne technique",
                  "type": f["type"], "nom": f["nom"], "definition": f["definition"], "exemples": f["exemples"],
                  "terme_lie": f["terme_lie"], "motif_rejet": f["motif_rejet"] or ""} for f in fiches]

    consigne = f"""Tu es l'assistant du DPO et de la conformité d'une entreprise (standard groupe), domaine {domaine}.
Classifie chaque élément, métier (glossaire) comme technique (colonne), selon la charte :
- confidentialite : une valeur parmi {regles["classification"]["confidentialite"]} ;
  "Restreint" est réservé aux données très sensibles (coordonnées bancaires, données personnelles sensibles, secrets d'affaires).
- donnee_personnelle : "Oui" si l'élément permet d'identifier directement ou indirectement une personne, sinon "Non".
- reglementee : "Oui" si c'est une donnée réglementée ({regles["definition_reglementee"]}), sinon "Non".
- Les trois axes sont indépendants. Pour une colonne, appuie-toi aussi sur ses exemples de valeurs.
- Si un motif_rejet est fourni, corrige en conséquence.

Éléments : {json.dumps(a_classer, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, confidentialite, donnee_personnelle, reglementee, justification."""

    print(f"{AGENT} : classification de {len(fiches)} fiche(s) du domaine {domaine}…")
    reponses = {p.get("id"): p for p in demander_gemini(consigne) if isinstance(p, dict)}

    # Termes d'abord (ils portent la classification), colonnes ensuite (elles en héritent)
    termes = {t["id"]: dict(t) for t in lire_fiches(domaine=domaine, chemin="B")}
    nb_critiques, nb_ecarts = 0, 0
    for f in sorted(fiches, key=lambda x: x["chemin"] != "B"):
        p = reponses.get(f["id"])
        if p is None:
            print(f"  {f['id']} : pas de réponse de Gemini, la fiche reste en attente.")
            continue
        classe = valeurs_valides(p, regles)
        if f["chemin"] == "B":
            heritage, ecarts = "porteur (terme métier)", []
            termes[f["id"]].update(classe)   # disponible pour l'héritage des colonnes
        else:
            id_terme = terme_parent(f, termes)
            classe, heritage, ecarts = classer_colonne(classe, termes.get(id_terme, {}), id_terme, regles)

        critique = est_critique(classe)
        nb_critiques += critique
        nb_ecarts += bool(ecarts)
        texte = (f"Classification DPO : {classe['confidentialite']}, personnelle {classe['donnee_personnelle']}, "
                 f"réglementée {classe['reglementee']} ; {heritage}.")
        if ecarts:
            texte += " Écart d'héritage : " + " ; ".join(ecarts) + "."
        mettre_a_jour(f["id"], AGENT, "Classification proposée", {
            **classe,
            "critique": "Oui" if critique else "Non",
            "heritage": heritage,
            "statut": "À valider",
            "acteur_suivant": SUIVANT,
            "commentaire_ia": (f["commentaire_ia"] or "") + " | " + texte + " " + p.get("justification", ""),
        }, detail=texte)
    print(f"{AGENT} : classification terminée ({nb_critiques} critique(s), {nb_ecarts} écart(s) d'héritage), relais à {SUIVANT}.")
