"""Génère les données FICTIVES d'un standard dans son dossier donnees/ (plomberie commune).

- glossaire_metier.xlsx       : chemin B (Domaine > Business Object > Business Terms et KPI)
- metadonnees_techniques.xlsx : chemin A (système > table > colonne, avec exemples de valeurs)
Les registres (qui est responsable de quel domaine) ne sont PAS générés ici : ils vivent dans config/.

Usage : appelé par le lanceur du standard, ou à la main depuis la racine du projet :
    python -m commun.generer_donnees groupe
"""
import sys

import pandas as pd

from commun.outils import chemin, utiliser_standard

# ===== CHEMIN B : glossaire métier (même périmètre fictif pour les deux organisations) =====
glossaire = [
    ("Supply Chain", "Lot de production", "Business Object", "Lot de production"),
    ("Supply Chain", "Lot de production", "Business Term", "Numéro de lot"),
    ("Supply Chain", "Lot de production", "Business Term", "Date de fabrication"),
    ("Supply Chain", "Lot de production", "Business Term", "Date de péremption"),
    ("Supply Chain", "Lot de production", "Business Term", "Statut de libération qualité"),
    ("Supply Chain", "Lot de production", "KPI", "Délai de libération des lots"),
    ("Supply Chain", "Lot de production", "KPI", "Taux de lots rejetés"),
    ("Supply Chain", "Ordre de fabrication", "Business Object", "Ordre de fabrication"),
    ("Supply Chain", "Ordre de fabrication", "Business Term", "Quantité planifiée"),
    ("Supply Chain", "Ordre de fabrication", "Business Term", "Date de début de production"),
    ("Supply Chain", "Ordre de fabrication", "Business Term", "Site de production"),
    ("Supply Chain", "Ordre de fabrication", "KPI", "Taux de rendement"),
    ("Supply Chain", "Entrepôt", "Business Object", "Entrepôt"),
    ("Supply Chain", "Entrepôt", "Business Term", "Emplacement"),
    ("Supply Chain", "Entrepôt", "Business Term", "Capacité de stockage"),
    ("Supply Chain", "Entrepôt", "KPI", "Taux de rotation des stocks"),
    ("Supply Chain", "Transport", "Business Object", "Transport"),
    ("Supply Chain", "Transport", "Business Term", "Mode de transport"),
    ("Supply Chain", "Transport", "Business Term", "Incoterm"),
    ("Supply Chain", "Transport", "KPI", "Taux de livraison à l'heure"),
    ("Finance", "Fournisseur", "Business Object", "Fournisseur"),
    ("Finance", "Fournisseur", "Business Term", "Raison sociale du fournisseur"),
    ("Finance", "Fournisseur", "Business Term", "Coordonnées bancaires du fournisseur"),
    ("Finance", "Facture fournisseur", "Business Object", "Facture fournisseur"),
    ("Finance", "Facture fournisseur", "Business Term", "Montant hors taxes"),
    ("Finance", "Facture fournisseur", "Business Term", "Date d'échéance"),
    ("Finance", "Facture fournisseur", "KPI", "Délai moyen de paiement fournisseurs"),
]

# ===== CHEMIN A : métadonnées techniques fictives =====
technique = [
    ("Supply Chain", "ERP", "LOTS", "NUM_LOT", "texte", "L2026-0457 ; L2026-0458"),
    ("Supply Chain", "ERP", "LOTS", "DT_FABRIC", "date", "2026-09-12"),
    ("Supply Chain", "ERP", "LOTS", "DT_PEREMPTION", "date", "2028-09-30"),
    ("Supply Chain", "ERP", "LOTS", "STATUT_QA", "texte", "LIBERE ; BLOQUE ; EN_ATTENTE"),
    ("Supply Chain", "MES", "OF_PRODUCTION", "QTE_PLANIF", "nombre", "12000 ; 8500"),
    ("Supply Chain", "MES", "OF_PRODUCTION", "DT_DEBUT", "date", "2026-10-02"),
    ("Supply Chain", "MES", "OF_PRODUCTION", "CD_SITE", "texte", "SITE01 ; SITE02"),
    ("Supply Chain", "LIMS", "ANALYSES", "RESULTAT_CQ", "texte", "CONFORME ; NON_CONFORME"),
    ("Supply Chain", "WMS", "ENTREPOTS", "TEMP_STOCK_MAX", "nombre", "8 ; 25"),
    ("Supply Chain", "WMS", "STOCKS", "QTE_DISPO", "nombre", "1200 ; 0"),
    ("Supply Chain", "WMS", "STOCKS", "CD_EMPLACEMENT", "texte", "A-12-03 ; B-01-07"),
    ("Supply Chain", "TMS", "EXPEDITIONS", "MODE_TRANSPORT", "texte", "ROUTE ; AERIEN"),
    ("Supply Chain", "DATAMART", "KPI_SC", "TX_OTD", "nombre", "0.94 ; 0.97"),
    ("Finance", "ERP", "FOURNISSEURS", "RAISON_SOCIALE", "texte", "Fournisseur Alpha (fictif)"),
    ("Finance", "ERP", "FOURNISSEURS", "IBAN", "texte", "FR76 XXXX (fictif)"),
    ("Finance", "ERP", "FACTURES", "MNT_HT", "nombre", "1250.00 ; 87.40"),
    ("Finance", "ERP", "FACTURES", "DT_ECHEANCE", "date", "2026-11-30"),
    ("Finance", "ERP", "GL_ECRITURES", "CPT_GL_NUM", "texte", "401000 ; 512100"),
]


def generer():
    """Écrit les deux fichiers Excel dans le dossier donnees/ du standard actif. Renvoie (nb termes, nb colonnes)."""
    dossier = chemin("donnees")
    dossier.mkdir(parents=True, exist_ok=True)

    df_glossaire = pd.DataFrame(glossaire, columns=["domaine", "business_object", "type", "nom"])
    df_glossaire.insert(0, "id", [f"GLO-{i:02d}" for i in range(1, len(df_glossaire) + 1)])
    df_glossaire["definition"] = ""
    df_glossaire["chemin"] = "B"
    df_glossaire["statut"] = "Identifié"
    df_glossaire.to_excel(dossier / "glossaire_metier.xlsx", index=False)

    df_technique = pd.DataFrame(technique, columns=["domaine", "systeme", "table", "colonne", "type_donnee", "exemples"])
    df_technique.insert(0, "id", [f"TEC-{i:02d}" for i in range(1, len(df_technique) + 1)])
    df_technique["terme_lie"] = ""
    df_technique["chemin"] = "A"
    df_technique["statut"] = "Identifié"
    df_technique.to_excel(dossier / "metadonnees_techniques.xlsx", index=False)
    return len(df_glossaire), len(df_technique)


if __name__ == "__main__":
    utiliser_standard(sys.argv[1] if len(sys.argv) > 1 else "groupe")
    nb_termes, nb_colonnes = generer()
    print(f"Données générées dans {chemin('donnees')} : {nb_termes} éléments de glossaire, {nb_colonnes} colonnes techniques.")
