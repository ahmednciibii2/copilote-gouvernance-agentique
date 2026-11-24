"""AG-BIS-CROISEMENT-AB — croisement A→B du standard bis (tâche M4 du Data Manager).

Part d'une colonne technique (chemin A) et cherche le terme du glossaire qu'elle représente.
- Terme trouvé : le lien est écrit dans terme_lie.
- Aucun terme : écart A→B, un terme « NOUVEAU : nom (Business Object) » est proposé avec sa définition.
Relais ensuite à l'agent DPO pour la classification.
"""
import json
import re

from commun.outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour, utiliser_standard

STANDARD = "bis"
AGENT = "AG-BIS-CROISEMENT-AB"
SUIVANT = "AG-BIS-DPO"
utiliser_standard(STANDARD)


def _nettoyer(texte):
    """Retire un éventuel préfixe « NOUVEAU : » (même répété) d'un libellé."""
    return re.sub(r"^(\s*NOUVEAU\s*:?\s*)+", "", texte or "", flags=re.IGNORECASE).strip()


def interpreter_rattachement(proposition, termes_connus):
    """Renvoie (terme_lie, definition, nouveau, commentaire) à partir de la proposition de Gemini."""
    lien = (proposition.get("terme_lie") or "").strip()
    if lien in termes_connus:
        return lien, "", False, f"Croisement A→B : rattachée au terme existant {lien} ({termes_connus[lien]})."
    nom_terme = _nettoyer(proposition.get("nouveau_terme")) or _nettoyer(lien)
    objet = _nettoyer(proposition.get("business_object"))
    definition = proposition.get("definition", "")
    texte = f"Croisement A→B : écart A→B, nouveau terme métier proposé : {nom_terme}, dans {objet}. Définition proposée : {definition}"
    return f"NOUVEAU : {nom_terme} ({objet})", definition, True, texte


def rattacher_colonnes(domaine):
    """Rattache chaque colonne technique à un terme métier, ou propose un nouveau terme ; relais à l'agent DPO."""
    acteurs = infos_domaine(domaine)
    regles = charger_regles()
    colonnes = [c for c in lire_fiches(domaine=domaine, chemin="A") if c["statut"] in ("Identifié", "À corriger")]
    if not colonnes:
        print(f"{AGENT} : aucune colonne technique à rattacher pour {domaine}.")
        return

    termes = lire_fiches(domaine=domaine, chemin="B")
    deja_lies = {}
    for t in termes:
        for i in (t["colonnes_liees"] or "").split(","):
            if i.strip():
                deja_lies.setdefault(i.strip(), []).append(t["id"])

    a_traiter = [{
        "id": c["id"], "colonne": c["nom"], "exemples": c["exemples"],
        "deja_liee_depuis_le_glossaire": deja_lies.get(c["id"], []),
        "proposition_precedente": c["terme_lie"] or "",
        "motif_rejet": c["motif_rejet"] or "",
    } for c in colonnes]
    glossaire = [{"id": t["id"], "type": t["type"], "nom": t["nom"], "business_object": t["business_object"]} for t in termes]

    consigne = f"""Tu es l'assistant du Data Manager ({acteurs["data_manager"]}) du domaine {domaine} dans une entreprise.
Tu relies le SI au glossaire métier : pour chaque colonne technique, trouve l'élément du glossaire qu'elle représente.
- terme_lie : l'id de l'élément du glossaire correspondant ; si aucun ne convient, écris exactement "NOUVEAU".
- Si "NOUVEAU" : propose nouveau_terme (nom en langage métier, sans le mot NOUVEAU), business_object (un Business Object existant du glossaire si possible) et definition ({regles["regle_definition"]}).
- Sinon : nouveau_terme, business_object et definition sont des chaînes vides.
- Tiens compte des liens déjà faits depuis le glossaire (deja_liee_depuis_le_glossaire) pour rester cohérent.
- Si un motif_rejet est fourni, corrige ta proposition_precedente en conséquence.

Colonnes techniques : {json.dumps(a_traiter, ensure_ascii=False)}
Glossaire métier : {json.dumps(glossaire, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés id, terme_lie, nouveau_terme, business_object, definition, justification."""

    print(f"{AGENT} : croisement A→B de {len(colonnes)} colonne(s) du domaine {domaine}…")
    noms = {t["id"]: t["nom"] for t in termes}
    propositions = {p.get("id"): p for p in demander_gemini(consigne) if isinstance(p, dict)}

    nb_nouveaux = 0
    for c in colonnes:
        p = propositions.get(c["id"])
        if p is None:
            print(f"  {c['id']} : pas de réponse de Gemini, la colonne reste en attente.")
            continue
        terme, definition, nouveau, texte = interpreter_rattachement(p, noms)
        nb_nouveaux += 1 if nouveau else 0
        mettre_a_jour(c["id"], AGENT, "Croisement A→B proposé", {
            "terme_lie": terme,
            "definition": definition,
            "statut": "En rédaction",
            "acteur_suivant": SUIVANT,
            "commentaire_ia": texte + " " + p.get("justification", ""),
        }, detail=texte)
    print(f"{AGENT} : rattachements proposés, dont {nb_nouveaux} nouveau(x) terme(s) (écarts A→B) ; relais à {SUIVANT}.")
