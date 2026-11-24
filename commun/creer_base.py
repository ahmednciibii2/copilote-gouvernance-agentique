"""Création de la base du catalogue d'un standard (plomberie commune, aucune règle métier).

Usage (depuis le lanceur du standard, après utiliser_standard) :
    from commun.creer_base import initialiser
    initialiser()            # lit les Excel du dossier donnees/ du standard actif
"""
from datetime import datetime

import pandas as pd

from commun.outils import chemin, connexion


def initialiser(dossier_donnees=None):
    """Crée (ou recrée) la base du standard actif et charge ses fichiers Excel. Renvoie le nombre de fiches."""
    dossier = dossier_donnees or chemin("donnees")
    maintenant = datetime.now().isoformat(timespec="seconds")
    con = connexion(creer=True)
    cur = con.cursor()

    cur.execute("DROP TABLE IF EXISTS fiches")
    cur.execute("DROP TABLE IF EXISTS historique")

    cur.execute("""
    CREATE TABLE fiches (
        id TEXT PRIMARY KEY,
        chemin TEXT, domaine TEXT, type TEXT, nom TEXT,
        business_object TEXT, systeme TEXT, table_source TEXT, colonne TEXT, exemples TEXT,
        definition TEXT, formule TEXT,
        confidentialite TEXT, donnee_personnelle TEXT, reglementee TEXT, critique TEXT,
        heritage TEXT,
        terme_lie TEXT, colonnes_liees TEXT,
        statut TEXT, acteur_suivant TEXT, nb_rejets INTEGER DEFAULT 0,
        motif_rejet TEXT, commentaire_ia TEXT, maj_le TEXT
    )""")

    cur.execute("""
    CREATE TABLE historique (
        num INTEGER PRIMARY KEY AUTOINCREMENT,
        fiche_id TEXT, date TEXT, auteur TEXT, action TEXT,
        ancien_statut TEXT, nouveau_statut TEXT, detail TEXT
    )""")

    glossaire = pd.read_excel(f"{dossier}/glossaire_metier.xlsx", dtype=str).fillna("")
    for _, l in glossaire.iterrows():
        cur.execute(
            "INSERT INTO fiches (id, chemin, domaine, type, nom, business_object, statut, maj_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (l["id"], "B", l["domaine"], l["type"], l["nom"], l["business_object"], "Identifié", maintenant),
        )

    technique = pd.read_excel(f"{dossier}/metadonnees_techniques.xlsx", dtype=str).fillna("")
    for _, l in technique.iterrows():
        nom = f'{l["systeme"]}.{l["table"]}.{l["colonne"]}'
        cur.execute(
            "INSERT INTO fiches (id, chemin, domaine, type, nom, systeme, table_source, colonne, exemples, statut, maj_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (l["id"], "A", l["domaine"], "Colonne technique", nom, l["systeme"], l["table"], l["colonne"], l["exemples"], "Identifié", maintenant),
        )

    cur.execute(
        "INSERT INTO historique (fiche_id, date, auteur, action, nouveau_statut, detail) SELECT id, ?, 'Chargement initial', 'Import Excel', 'Identifié', chemin FROM fiches",
        (maintenant,),
    )
    con.commit()
    nb = cur.execute("SELECT COUNT(*) FROM fiches").fetchone()[0]
    con.close()
    return nb
