"""Faux Gemini pour les tests hors ligne : réponses prévisibles, aucun appel réseau, aucun quota."""
import re


def faux_gemini(consigne, essais=3):
    """Répond comme Gemini, de façon prévisible, à n'importe quelle consigne des agents."""
    reponses = []
    for i in sorted(set(re.findall(r'"id": "([A-Z]{3}-\d+)"', consigne))):
        r = {"id": i, "definition": f"Définition de test pour {i}.", "formule": "lots refusés / lots fabriqués (mois)", "justification": "test",
             "colonnes_liees": {"GLO-02": ["TEC-01"], "GLO-23": ["TEC-15"]}.get(i, []),
             "terme_lie": {"TEC-01": "GLO-02", "TEC-15": "GLO-23"}.get(i, "NOUVEAU"), "nouveau_terme": f"Terme {i}", "business_object": "Lot de production",
             "confidentialite": "Restreint" if i in ("TEC-01", "TEC-15") else "Interne", "donnee_personnelle": "Non",
             "reglementee": "Oui" if i in ("GLO-02", "TEC-01") else "Non",
             "synthese": "Synthèse de test.", "recommandation": "Valider", "motif": "", "points_attention": ""}
        for p in ("C2", "C3", "C4", "C5"):
            r[p] = {"resultat": "ko" if (i == "GLO-03" and p == "C4") else "ok", "motif": "colonne d'un autre objet" if i == "GLO-03" else ""}
        reponses.append(r)
    return reponses
