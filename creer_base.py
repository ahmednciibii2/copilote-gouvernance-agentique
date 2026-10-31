import sqlite3
from datetime import datetime
import pandas as pd

maintenant = datetime.now().isoformat(timespec="seconds")

# 1. Ouvrir (ou créer) la base
con = sqlite3.connect("catalogue.db")
cur = con.cursor()

# 2. Repartir de zéro à chaque lancement
cur.execute("DROP TABLE IF EXISTS fiches")
cur.execute("DROP TABLE IF EXISTS historique")

# 3. Table des fiches du catalogue
cur.execute("""
CREATE TABLE fiches (
    id TEXT PRIMARY KEY,
    chemin TEXT, domaine TEXT, type TEXT, nom TEXT,
    business_object TEXT, systeme TEXT, table_source TEXT, colonne TEXT, exemples TEXT,
    definition TEXT, formule TEXT,
    confidentialite TEXT, donnee_personnelle TEXT, gxp TEXT, critique TEXT,
    terme_lie TEXT, colonnes_liees TEXT,
    statut TEXT, acteur_suivant TEXT, nb_rejets INTEGER DEFAULT 0,
    motif_rejet TEXT, commentaire_ia TEXT, maj_le TEXT
)""")

# 4. Table de l'historique (traçabilité)
cur.execute("""
CREATE TABLE historique (
    num INTEGER PRIMARY KEY AUTOINCREMENT,
    fiche_id TEXT, date TEXT, auteur TEXT, action TEXT,
    ancien_statut TEXT, nouveau_statut TEXT, detail TEXT
)""")

# 5. Charger le glossaire métier (chemin B)
glossaire = pd.read_excel("donnees/glossaire_metier.xlsx", dtype=str).fillna("")
for _, l in glossaire.iterrows():
    cur.execute(
        "INSERT INTO fiches (id, chemin, domaine, type, nom, business_object, statut, maj_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (l["id"], "B", l["domaine"], l["type"], l["nom"], l["business_object"], "Identifié", maintenant),
    )

# 6. Charger les métadonnées techniques (chemin A)
technique = pd.read_excel("donnees/metadonnees_techniques.xlsx", dtype=str).fillna("")
for _, l in technique.iterrows():
    nom = f'{l["systeme"]}.{l["table"]}.{l["colonne"]}'
    cur.execute(
        "INSERT INTO fiches (id, chemin, domaine, type, nom, systeme, table_source, colonne, exemples, statut, maj_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (l["id"], "A", l["domaine"], "Colonne technique", nom, l["systeme"], l["table"], l["colonne"], l["exemples"], "Identifié", maintenant),
    )

# 7. Tracer le chargement dans l'historique
cur.execute(
    "INSERT INTO historique (fiche_id, date, auteur, action, nouveau_statut, detail) SELECT id, ?, 'Chargement initial', 'Import Excel', 'Identifié', chemin FROM fiches",
    (maintenant,),
)
con.commit()

# 8. Contrôle
print("Fiches chargées :", cur.execute("SELECT COUNT(*) FROM fiches").fetchone()[0])
for chemin, n in cur.execute("SELECT chemin, COUNT(*) FROM fiches GROUP BY chemin"):
    print("  Chemin", chemin, ":", n)
print("Lignes d'historique :", cur.execute("SELECT COUNT(*) FROM historique").fetchone()[0])
con.close()