import os

from flask import Flask, redirect, render_template_string, request, url_for

import outils

SCENARIOS = {
    "groupe": ("catalogue_groupe.db", "donnees/registre_standard_groupe.xlsx"),
    "bis": ("catalogue_bis.db", "donnees/registre_standard_bis.xlsx"),
}
REDACTEUR = {"groupe": "AG-GRP-STEWARD", "bis": "AG-BIS-MANAGER"}
CHAMPS = [
    ("Id", "id"), ("Domaine", "domaine"), ("Chemin", "chemin"), ("Type", "type"),
    ("Business Object", "business_object"), ("Système", "systeme"), ("Table", "table_source"),
    ("Colonne", "colonne"), ("Exemples", "exemples"), ("Définition", "definition"), ("Formule", "formule"),
    ("Confidentialité", "confidentialite"), ("Donnée personnelle", "donnee_personnelle"), ("GxP", "gxp"),
    ("Critique", "critique"), ("Terme lié (A→B)", "terme_lie"), ("Colonnes liées (B→A)", "colonnes_liees"),
    ("Acteur suivant", "acteur_suivant"), ("Nombre de rejets", "nb_rejets"), ("Motif de rejet", "motif_rejet"),
    ("Commentaires des agents", "commentaire_ia"),
]

STYLE = """<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1f2937;background:#f8fafc}
h1{font-size:22px} h2{font-size:18px} a{color:#1d4ed8;text-decoration:none}
table{border-collapse:collapse;width:100%;background:#fff}
th,td{border:1px solid #e5e7eb;padding:6px 8px;font-size:14px;text-align:left;vertical-align:top}
th{background:#f1f5f9;width:200px}
.badge{padding:2px 8px;border-radius:10px;font-size:12px;background:#e2e8f0;margin-right:6px}
.critique{background:#fee2e2} .certifie{background:#dcfce7} .bloque{background:#fde68a}
.onglets a{display:inline-block;margin-right:8px;padding:6px 12px;border-radius:6px;background:#e2e8f0}
.onglets a.actif{background:#1d4ed8;color:#fff}
.carte{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:12px 0}
button{padding:6px 12px;margin:4px 8px 4px 0;cursor:pointer} textarea{width:100%;height:60px}
.erreur{color:#b91c1c;font-weight:bold}
</style>"""

PAGE_ACCUEIL = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Mini-catalogue</title>{{ style|safe }}</head><body>
<h1>Mini-catalogue de gouvernance — standard {{ scenario }}</h1>
<div class="onglets">
  <a href="{{ url_for('accueil', scenario='groupe') }}" class="{{ 'actif' if scenario == 'groupe' else '' }}">Standard groupe</a>
  <a href="{{ url_for('accueil', scenario='bis') }}" class="{{ 'actif' if scenario == 'bis' else '' }}">Standard bis</a>
</div>
{% if absente %}
  <p>La base de ce scénario n'existe pas encore : lancez <code>python main.py</code>.</p>
{% else %}
  <div class="carte"><b>Qui doit agir (cliquer pour filtrer)</b><br>
  {% for nom, n in corbeilles %}<a href="{{ url_for('accueil', scenario=scenario, acteur=nom) }}">{{ nom }} ({{ n }})</a>{% if not loop.last %} · {% endif %}{% endfor %}
  · <a href="{{ url_for('accueil', scenario=scenario) }}"><b>Tout afficher</b></a></div>
  <div class="carte"><b>Statuts :</b> {% for s, n in statuts %}<span class="badge">{{ s }} : {{ n }}</span>{% endfor %}</div>
  <h2>{{ titre }} ({{ fiches|length }})</h2>
  <table><tr><th>Id</th><th>Domaine</th><th>Type</th><th>Nom</th><th>Critique</th><th>Statut</th><th>Acteur suivant</th></tr>
  {% for f in fiches %}
    <tr class="{{ 'certifie' if f.statut == 'Certifié' else ('bloque' if f.statut == 'Bloqué' else ('critique' if f.critique == 'Oui' else '')) }}">
      <td><a href="{{ url_for('fiche', scenario=scenario, fiche_id=f.id) }}">{{ f.id }}</a></td>
      <td>{{ f.domaine }}</td><td>{{ f.type }}</td><td>{{ f.nom }}</td><td>{{ f.critique or '' }}</td>
      <td>{{ f.statut }}</td><td>{{ f.acteur_suivant or '' }}</td>
    </tr>
  {% endfor %}
  </table>
{% endif %}
</body></html>"""

PAGE_FICHE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{{ f.nom }}</title>{{ style|safe }}</head><body>
<p><a href="{{ url_for('accueil', scenario=scenario) }}">← Retour au catalogue (standard {{ scenario }})</a></p>
<h1>{{ f.nom }} <span class="badge">{{ f.statut }}</span>{% if f.critique == 'Oui' %}<span class="badge critique">Critique</span>{% endif %}</h1>
{% if actions %}
<div class="carte"><b>Décision de {{ decideur }}</b>
  {% if erreur %}<p class="erreur">Un motif est obligatoire pour renvoyer la fiche.</p>{% endif %}
  <form method="post" action="{{ url_for('decider', scenario=scenario, fiche_id=f.id) }}">
    {% for valeur, libelle in actions %}<button name="action" value="{{ valeur }}">{{ libelle }}</button>{% endfor %}
    <p>Motif ou commentaire (obligatoire pour renvoyer) :</p><textarea name="motif"></textarea>
  </form>
</div>
{% endif %}
<div class="carte"><table>
{% for libelle, cle in champs %}{% if f[cle] not in (None, '') %}<tr><th>{{ libelle }}</th><td>{{ f[cle] }}</td></tr>{% endif %}{% endfor %}
</table></div>
<h2>Historique (traçabilité)</h2>
<table><tr><th>Date</th><th>Auteur</th><th>Action</th><th>Statut avant</th><th>Statut après</th><th>Détail</th></tr>
{% for h in historique %}<tr><td>{{ h.date }}</td><td>{{ h.auteur }}</td><td>{{ h.action }}</td><td>{{ h.ancien_statut or '' }}</td><td>{{ h.nouveau_statut or '' }}</td><td>{{ h.detail or '' }}</td></tr>{% endfor %}
</table>
</body></html>"""

app = Flask(__name__)


def choisir(scenario):
    """Active la base et le registre du scénario demandé."""
    if scenario not in SCENARIOS:
        scenario = "groupe"
    base, registre = SCENARIOS[scenario]
    outils.utiliser(base, registre)
    return scenario


def lire_historique(fiche_id):
    con = outils.connexion()
    lignes = [dict(l) for l in con.execute("SELECT * FROM historique WHERE fiche_id = ? ORDER BY num", (fiche_id,))]
    con.close()
    return lignes


def actions_possibles(scenario, f):
    """Boutons proposés, uniquement si c'est au tour d'un humain d'agir."""
    suivant = f["acteur_suivant"] or ""
    if not suivant.endswith("(humain)"):
        return []
    if f["statut"] == "Bloqué":
        return [("renvoyer", "Renvoyer au rédacteur avec ma décision")]
    if scenario == "bis" and suivant.startswith("Data Governance Leader"):
        return [("confirmer", "Confirmer l'élément critique"), ("renvoyer", "Renvoyer avec motif")]
    return [("publier", "Publier (Certifié)"), ("renvoyer", "Renvoyer avec motif")]


@app.route("/")
def accueil():
    scenario = choisir(request.args.get("scenario", "groupe"))
    if not os.path.exists(SCENARIOS[scenario][0]):
        return render_template_string(PAGE_ACCUEIL, style=STYLE, scenario=scenario, absente=True)

    toutes = sorted(outils.lire_fiches(), key=lambda f: (f["domaine"], f["id"]))
    corbeilles, statuts = {}, {}
    for f in toutes:
        nom = f["acteur_suivant"] or "Personne (terminé)"
        corbeilles[nom] = corbeilles.get(nom, 0) + 1
        statuts[f["statut"]] = statuts.get(f["statut"], 0) + 1

    acteur = request.args.get("acteur", "")
    fiches = [f for f in toutes if not acteur or (f["acteur_suivant"] or "Personne (terminé)") == acteur]
    return render_template_string(
        PAGE_ACCUEIL, style=STYLE, scenario=scenario, absente=False, fiches=fiches,
        corbeilles=sorted(corbeilles.items(), key=lambda x: -x[1]), statuts=sorted(statuts.items()),
        titre=f"Corbeille : {acteur}" if acteur else "Toutes les fiches",
    )


@app.route("/fiche/<scenario>/<fiche_id>")
def fiche(scenario, fiche_id):
    scenario = choisir(scenario)
    f = outils.lire_fiches(id=fiche_id)[0]
    return render_template_string(
        PAGE_FICHE, style=STYLE, scenario=scenario, f=f, champs=CHAMPS,
        historique=lire_historique(fiche_id), actions=actions_possibles(scenario, f),
        decideur=(f["acteur_suivant"] or "").replace(" (humain)", ""), erreur=request.args.get("erreur"),
    )


@app.route("/fiche/<scenario>/<fiche_id>/decision", methods=["POST"])
def decider(scenario, fiche_id):
    scenario = choisir(scenario)
    f = outils.lire_fiches(id=fiche_id)[0]
    if not actions_possibles(scenario, f):
        return redirect(url_for("fiche", scenario=scenario, fiche_id=fiche_id))

    auteur = (f["acteur_suivant"] or "Humain").replace(" (humain)", "")
    action = request.form.get("action")
    motif = request.form.get("motif", "").strip()

    if action == "publier":
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : publication", {
            "statut": "Certifié", "acteur_suivant": "", "motif_rejet": "",
        }, detail=motif)
    elif action == "confirmer":
        manager = outils.infos_domaine(f["domaine"])["data_manager"]
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : élément critique confirmé", {
            "statut": "À valider", "acteur_suivant": f"Data Manager : {manager} (humain)",
        }, detail=motif)
    elif action == "renvoyer":
        if not motif:
            return redirect(url_for("fiche", scenario=scenario, fiche_id=fiche_id, erreur=1))
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : renvoi au rédacteur", {
            "statut": "À corriger", "acteur_suivant": REDACTEUR[scenario],
            "nb_rejets": 0, "motif_rejet": "Décision humaine : " + motif,
        }, detail=motif)
    return redirect(url_for("fiche", scenario=scenario, fiche_id=fiche_id))


if __name__ == "__main__":
    app.run(port=5002, debug=True)