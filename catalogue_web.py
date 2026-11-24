"""Catalogue web du POC — une page, deux espaces séparés : /groupe et /bis.

Chaque espace lit UNIQUEMENT la base de son standard (standard_groupe/catalogue.db ou standard_bis/catalogue.db).
Les humains y prennent les décisions : publier, renvoyer, confirmer (fiches critiques du bis).
Lancement, depuis la racine du projet :  python catalogue_web.py   puis  http://127.0.0.1:5002
"""
import re

from flask import Flask, abort, redirect, render_template_string, request, url_for

import commun.outils as outils

STANDARDS = {
    "groupe": {"titre": "Standard groupe", "organisation": "Data Owner + Data Steward + Data Custodian + Data Governance Leader",
               "redacteur": "AG-GRP-STEWARD", "custodian": "AG-GRP-CUSTODIAN"},
    "bis": {"titre": "Standard bis", "organisation": "Data Manager + Data Custodian + Data Governance Leader",
            "redacteur": "AG-BIS-MANAGER", "custodian": "AG-BIS-CUSTODIAN"},
}
CHAMPS = [
    ("Id", "id"), ("Domaine", "domaine"), ("Chemin", "chemin"), ("Type", "type"),
    ("Business Object", "business_object"), ("Système", "systeme"), ("Table", "table_source"),
    ("Colonne", "colonne"), ("Exemples", "exemples"), ("Lignage", "lignage"),
    ("Description technique", "description_technique"), ("Règle qualité", "regle_qualite"),
    ("Définition", "definition"), ("Formule", "formule"),
    ("Confidentialité", "confidentialite"), ("Donnée personnelle", "donnee_personnelle"), ("Réglementée", "reglementee"),
    ("Critique", "critique"), ("Héritage de classification", "heritage"),
    ("Terme lié (A→B)", "terme_lie"), ("Colonnes liées (B→A)", "colonnes_liees"),
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
.dossier th{width:170px} .grille{font-family:Consolas,monospace;font-size:15px}
.espaces{display:flex;gap:16px;flex-wrap:wrap} .espace{flex:1;min-width:280px}
.pied-page{margin-top:40px;padding-top:12px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;text-align:center}
</style>"""

PIED = '<div class="pied-page">POC gouvernance agentique — données fictives — Gemini</div>'

PAGE_ACCUEIL_GENERAL = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Catalogue de gouvernance</title>{{ style|safe }}</head><body>
<h1>Catalogue de gouvernance — deux organisations, deux espaces séparés</h1>
<div class="espaces">
{% for code, s, nb in espaces %}
  <div class="carte espace"><h2><a href="{{ url_for('accueil', std=code) }}">{{ s.titre }} →</a></h2>
  <p>{{ s.organisation }}</p>
  <p>{% if nb is none %}<i>Base pas encore créée : <code>python -m standard_{{ code }}.lancer</code></i>{% else %}{{ nb }} fiches{% endif %}</p></div>
{% endfor %}
</div>
{{ pied|safe }}</body></html>"""

PAGE_ACCUEIL = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{{ s.titre }}</title>{{ style|safe }}</head><body>
<p><a href="{{ url_for('general') }}">← Les deux espaces</a></p>
<h1>{{ s.titre }} <span class="badge">{{ s.organisation }}</span></h1>
<div class="onglets">
  <a href="{{ url_for('accueil', std='groupe') }}" class="{{ 'actif' if std == 'groupe' else '' }}">Standard groupe</a>
  <a href="{{ url_for('accueil', std='bis') }}" class="{{ 'actif' if std == 'bis' else '' }}">Standard bis</a>
</div>
{% if absente %}
  <p>La base de ce standard n'existe pas encore : lancez <code>python -m standard_{{ std }}.lancer</code>.</p>
{% else %}
  <div class="carte"><b>Qui doit agir (cliquer pour filtrer)</b><br>
  {% for nom, n in corbeilles %}<a href="{{ url_for('accueil', std=std, acteur=nom) }}">{{ nom }} ({{ n }})</a>{% if not loop.last %} · {% endif %}{% endfor %}
  · <a href="{{ url_for('accueil', std=std) }}"><b>Tout afficher</b></a></div>
  <div class="carte"><b>Statuts :</b> {% for st, n in statuts %}<span class="badge">{{ st }} : {{ n }}</span>{% endfor %}</div>
  <h2>{{ titre }} ({{ fiches|length }})</h2>
  <table><tr><th>Id</th><th>Domaine</th><th>Type</th><th>Nom</th><th>Critique</th><th>Statut</th><th>Acteur suivant</th></tr>
  {% for f in fiches %}
    <tr class="{{ 'certifie' if f.statut == 'Certifié' else ('bloque' if f.statut == 'Bloqué' else ('critique' if f.critique == 'Oui' else '')) }}">
      <td><a href="{{ url_for('fiche', std=std, fiche_id=f.id) }}">{{ f.id }}</a></td>
      <td>{{ f.domaine }}</td><td>{{ f.type }}</td><td>{{ f.nom }}</td><td>{{ f.critique or '' }}</td>
      <td>{{ f.statut }}</td><td>{{ f.acteur_suivant or '' }}</td>
    </tr>
  {% endfor %}
  </table>
{% endif %}
{{ pied|safe }}</body></html>"""

PAGE_FICHE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{{ f.nom }}</title>{{ style|safe }}</head><body>
<p><a href="{{ url_for('accueil', std=std) }}">← Retour à l'espace {{ s.titre }}</a></p>
<h1>{{ f.nom }} <span class="badge">{{ f.statut }}</span>{% if f.critique == 'Oui' %}<span class="badge critique">Critique</span>{% endif %}</h1>
{% if actions %}
<div class="carte"><b>Décision de {{ decideur }}</b>
  {% if erreur %}<p class="erreur">Un motif est obligatoire pour renvoyer la fiche.</p>{% endif %}
  <form method="post" action="{{ url_for('decider', std=std, fiche_id=f.id) }}">
    {% for valeur, libelle in actions %}<button name="action" value="{{ valeur }}">{{ libelle }}</button>{% endfor %}
    <p>Motif ou commentaire (obligatoire pour renvoyer) :</p><textarea name="motif"></textarea>
  </form>
</div>
{% endif %}
{% if grille %}<div class="carte"><b>Contrôle du Leader (grille C1 à C7)</b><p class="grille">{{ grille }}</p></div>{% endif %}
{% if dossier %}<div class="carte"><b>Dossier de décision préparé par l'agent</b>
<table class="dossier">{% for rubrique, valeur in dossier %}<tr><th>{{ rubrique }}</th><td>{{ valeur }}</td></tr>{% endfor %}</table></div>{% endif %}
<div class="carte"><table>
{% for libelle, cle in champs %}{% if f[cle] not in (None, '') %}<tr><th>{{ libelle }}</th><td>{{ f[cle] }}</td></tr>{% endif %}{% endfor %}
</table></div>
<h2>Historique (traçabilité)</h2>
<table><tr><th>Date</th><th>Auteur</th><th>Action</th><th>Statut avant</th><th>Statut après</th><th>Détail</th></tr>
{% for h in historique %}<tr><td>{{ h.date }}</td><td>{{ h.auteur }}</td><td>{{ h.action }}</td><td>{{ h.ancien_statut or '' }}</td><td>{{ h.nouveau_statut or '' }}</td><td>{{ h.detail or '' }}</td></tr>{% endfor %}
</table>
{{ pied|safe }}</body></html>"""

app = Flask(__name__)


def activer(std):
    """Règle la boîte à outils sur le standard de l'espace demandé (404 si inconnu)."""
    if std not in STANDARDS:
        abort(404)
    outils.utiliser_standard(std)
    return STANDARDS[std]


def lire_historique(fiche_id):
    con = outils.connexion()
    lignes = [dict(l) for l in con.execute("SELECT * FROM historique WHERE fiche_id = ? ORDER BY num", (fiche_id,))]
    con.close()
    return lignes


def lire_dossier(f):
    """Retrouve dans les commentaires la grille du Leader et le dossier de décision (5 rubriques)."""
    texte = f["commentaire_ia"] or ""
    grille = re.search(r"Contrôle Leader : (C1 .*?C7 \S+)", texte)
    dossier = re.search(r"Dossier de décision — (.*)$", texte)
    rubriques = []
    if dossier:
        for morceau in dossier.group(1).split(" · "):
            nom, _, valeur = morceau.partition(" : ")
            rubriques.append((nom.strip(), valeur.strip()))
    return (grille.group(1) if grille else ""), rubriques


def actions_possibles(std, f):
    """Boutons proposés, uniquement si c'est au tour d'un humain d'agir."""
    suivant = f["acteur_suivant"] or ""
    if not suivant.endswith("(humain)"):
        return []
    if f["statut"] == "Bloqué":
        return [("renvoyer", "Renvoyer au rédacteur avec ma décision")]
    if std == "bis" and suivant.startswith("Data Governance Leader"):
        return [("confirmer", "Confirmer l'élément critique"), ("renvoyer", "Renvoyer avec motif")]
    return [("publier", "Publier (Certifié)"), ("renvoyer", "Renvoyer avec motif")]


@app.route("/")
def general():
    espaces = []
    for code, s in STANDARDS.items():
        outils.utiliser_standard(code)
        espaces.append((code, s, len(outils.lire_fiches()) if outils.BASE.exists() else None))
    return render_template_string(PAGE_ACCUEIL_GENERAL, style=STYLE, pied=PIED, espaces=espaces)


@app.route("/<std>")
def accueil(std):
    s = activer(std)
    if not outils.BASE.exists():
        return render_template_string(PAGE_ACCUEIL, style=STYLE, pied=PIED, std=std, s=s, absente=True)

    toutes = sorted(outils.lire_fiches(), key=lambda f: (f["domaine"], f["id"]))
    corbeilles, statuts = {}, {}
    for f in toutes:
        nom = f["acteur_suivant"] or "Personne (terminé)"
        corbeilles[nom] = corbeilles.get(nom, 0) + 1
        statuts[f["statut"]] = statuts.get(f["statut"], 0) + 1

    acteur = request.args.get("acteur", "")
    fiches = [f for f in toutes if not acteur or (f["acteur_suivant"] or "Personne (terminé)") == acteur]
    return render_template_string(
        PAGE_ACCUEIL, style=STYLE, pied=PIED, std=std, s=s, absente=False, fiches=fiches,
        corbeilles=sorted(corbeilles.items(), key=lambda x: -x[1]), statuts=sorted(statuts.items()),
        titre=f"Corbeille : {acteur}" if acteur else "Toutes les fiches",
    )


@app.route("/<std>/fiche/<fiche_id>")
def fiche(std, fiche_id):
    s = activer(std)
    trouvees = outils.lire_fiches(id=fiche_id)
    if not trouvees:
        abort(404)
    f = trouvees[0]
    grille, dossier = lire_dossier(f)
    return render_template_string(
        PAGE_FICHE, style=STYLE, pied=PIED, std=std, s=s, f=f, champs=CHAMPS, grille=grille, dossier=dossier,
        historique=lire_historique(fiche_id), actions=actions_possibles(std, f),
        decideur=(f["acteur_suivant"] or "").replace(" (humain)", ""), erreur=request.args.get("erreur"),
    )


@app.route("/<std>/fiche/<fiche_id>/decision", methods=["POST"])
def decider(std, fiche_id):
    s = activer(std)
    f = outils.lire_fiches(id=fiche_id)[0]
    if not actions_possibles(std, f):
        return redirect(url_for("fiche", std=std, fiche_id=fiche_id))

    auteur = (f["acteur_suivant"] or "Humain").replace(" (humain)", "")
    action = request.form.get("action")
    motif = request.form.get("motif", "").strip()

    if action == "publier":
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : publication", {
            "statut": "Certifié", "acteur_suivant": "", "motif_rejet": "",
        }, detail=motif)
    elif action == "confirmer":
        acteurs = outils.infos_domaine(f["domaine"])
        decideur = (f"Data Manager : {acteurs['data_manager']} (humain)" if f["chemin"] == "B"
                    else f"Data Custodian : {acteurs['data_custodian']} (humain)")
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : élément critique confirmé", {
            "statut": "À valider", "acteur_suivant": decideur,
        }, detail=motif)
    elif action == "renvoyer":
        if not motif:
            return redirect(url_for("fiche", std=std, fiche_id=fiche_id, erreur=1))
        # un terme repart au rédacteur, une colonne à l'agent Custodian
        retour = s["redacteur"] if f["chemin"] == "B" else s["custodian"]
        outils.mettre_a_jour(fiche_id, auteur, "Décision humaine : renvoi", {
            "statut": "À corriger", "acteur_suivant": retour,
            "nb_rejets": 0, "motif_rejet": "Décision humaine : " + motif,
        }, detail=motif)
    return redirect(url_for("fiche", std=std, fiche_id=fiche_id))


if __name__ == "__main__":
    app.run(port=5002, debug=True)
