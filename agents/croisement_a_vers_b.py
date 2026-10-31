import json
import re

from outils import charger_regles, demander_gemini, infos_domaine, lire_fiches, mettre_a_jour


def _nettoyer(texte):
    """Retire un éventuel préfixe « NOUVEAU : » (même répété) d'un libellé."""
    return re.sub(r"^(\s*NOUVEAU\s*:?\s*)+", "", texte or "", flags=re.IGNORECASE).strip()


def rattacher_colonnes(domaine):
    """Croisement A → B : rattache chaque colonne technique à un terme métier, ou propose un nouveau terme.
    Agit pour le Steward (standard groupe, tâche S4) ou le Data Manager (standard bis, tâche M4)."""
    infos = infos_domaine(domaine)
    groupe = infos["standard"] == "groupe"
    agent = "AG-GRP-STEWARD" if groupe else "AG-BIS-MANAGER"
    regles = charger_regles()

    colonnes = [c for c in lire_fiches(domaine=domaine, chemin="A") if c["statut"] in ("Identifié", "À corriger")]
    if not colonnes:
        print(f"{agent} : aucune colonne technique à rattacher pour {domaine}.")
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

    consigne = f"""Tu es l'assistant chargé de relier le SI au glossaire métier du domaine {domaine} dans un laboratoire pharmaceutique.
Pour chaque colonne technique, trouve l'élément du glossaire qu'elle représente.
- terme_lie : l'id de l'élément du glossaire correspondant ; si aucun ne convient, écris exactement "NOUVEAU".
- Si "NOUVEAU" : propose nouveau_terme (nom en langage métier, sans le mot NOUVEAU), business_object (un Business Object existant du glossaire si possible, sans le mot NOUVEAU) et definition ({regles["regle_definition"]}).
- Sinon : nouveau_terme, business_object et definition sont des chaînes vides.
- Tiens compte des liens déjà faits depuis le glossaire (deja_liee_depuis_le_glossaire) pour rester cohérent.
- confidentialite : une valeur parmi {regles["classification"]["confidentialite"]} (des coordonnées bancaires sont "Restreint").
- donnee_personnelle : "Oui" ou "Non" ; gxp : "Oui" si la donnée sert à garantir la qualité, la traçabilité ou la sécurité du médicament.
- Si un motif_rejet est fourni, corrige ta proposition_precedente en conséquence.

Colonnes techniques : {json.dumps(a_traiter, ensure_ascii=False)}
Glossaire métier : {json.dumps(glossaire, ensure_ascii=False)}

Réponds uniquement en JSON : une liste d'objets avec les clés
id, terme_lie, nouveau_terme, business_object, definition, confidentialite, donnee_personnelle, gxp, justification."""

    print(f"{agent} : croisement A → B de {len(colonnes)} colonne(s) du domaine {domaine}…")
    noms = {t["id"]: t["nom"] for t in termes}
    nb_nouveaux = 0
    for p in demander_gemini(consigne):
        if not isinstance(p, dict):
            continue
        critique = p.get("gxp") == "Oui" or p.get("donnee_personnelle") == "Oui" or p.get("confidentialite") == "Restreint"
        lien = (p.get("terme_lie") or "").strip()
        nouveau = lien.upper().startswith("NOUVEAU") or lien not in noms
        if nouveau:
            nb_nouveaux += 1
            nom_terme = _nettoyer(p.get("nouveau_terme")) or _nettoyer(lien)
            objet = _nettoyer(p.get("business_object"))
            terme = f"NOUVEAU : {nom_terme} ({objet})"
            texte = f"Nouveau terme métier proposé : {nom_terme}, dans {objet}. Définition proposée : {p.get('definition', '')} "
        else:
            terme = lien
            texte = f"Rattachée au terme existant {terme} ({noms.get(terme, '?')}). "

        if groupe:
            statut, suivant = "À valider", "AG-GRP-LEADER"
        elif critique:
            statut, suivant = "En confirmation", "AG-BIS-LEADER"
        else:
            statut, suivant = "À valider", f'Data Manager : {infos["data_manager"]} (humain)'

        mettre_a_jour(p.get("id"), agent, "Croisement A→B : rattachement proposé", {
            "terme_lie": terme,
            "definition": p.get("definition", "") if nouveau else "",
            "confidentialite": p.get("confidentialite", ""),
            "donnee_personnelle": p.get("donnee_personnelle", ""),
            "gxp": p.get("gxp", ""),
            "critique": "Oui" if critique else "Non",
            "statut": statut,
            "acteur_suivant": suivant,
            "commentaire_ia": "Croisement A→B proposé par IA, à valider. " + texte + p.get("justification", ""),
        }, detail=p.get("justification", ""))
    print(f"{agent} : rattachements proposés, dont {nb_nouveaux} nouveau(x) terme(s) métier à arbitrer.")