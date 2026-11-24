# Atelier du 24/11/2026 (suite) — Ajout du rôle Data Custodian, agent et humain

**Branche :** `atelier-2026-11-24-custodian` (créée depuis `main` au commit `fdf0d2c`, après la fusion de la PR #1)

## Objectif
Ajouter le **Data Custodian**, contrepartie technique du Data Steward (« The Implementer »), dans les deux standards :
un **agent** qui documente les métadonnées techniques et un **humain** qui décide sur les colonnes.
Il préparera aussi la suite : le scan de bases de données externes et d'APIs (chantier B) partira de lui.
Le DPO reste un agent seul pour le moment.

## Ce qui a été fait
| Élément | Contenu |
|---|---|
| Agent `custodian.py` (groupe et bis) | `documenter_colonnes` : description technique (rôle dans le modèle, format observé), lignage (système › table › colonne, calculé par le code), règle qualité proposée ; `preparer_decision` : dossier de décision des colonnes pour le Data Custodian humain |
| Circuit des colonnes | Custodian → Croisement A→B → Agent DPO → Leader (C1-C7) → Custodian (dossier) → **Data Custodian humain** ; en bis, une colonne critique est confirmée par le Data Governance Leader humain puis transmise au Data Custodian |
| Circuit des termes | Inchangé : rédacteur → Croisement B→A → DPO → Leader → Owner (groupe) / Manager (bis) → décideur métier |
| Leader / Leader bis | Refus d'une colonne → agent Custodian ; C1 exige description technique et règle qualité pour une colonne |
| Owner / Manager | Dossiers des termes uniquement |
| Registres | Colonne `data_custodian` : DC-FIN, DC-SC (noms fictifs) |
| Chartes 2.3 | Custodian dans l'organisation, les agents et le circuit ; champs obligatoires d'une colonne ; règle « colonne rattachée à un terme NOUVEAU » |
| Base | Champs `description_technique`, `lignage`, `regle_qualite` |
| Catalogue web | Champs techniques affichés ; renvoi d'une colonne → agent Custodian ; confirmation bis d'une colonne → Data Custodian |
| Tests | Contrôles Custodian ajoutés aux tests hors ligne et aux `test_standard` |

## Décisions prises
- Qui décide : **termes et KPI** → Data Owner (groupe) / Data Manager (bis) ; **colonnes techniques** → **Data Custodian**.
- Une colonne rattachée à un terme « NOUVEAU » est décidée par le Data Custodian ; la **création du terme** relève du décideur métier, et le dossier le rappelle.
- Le lignage est calculé par le code (pas par l'IA) ; la description technique et la règle qualité sont proposées par l'IA et validées par l'humain.

## État à la fin de la séance
- ✅ Tests hors ligne : groupe 13/13, bis 14/14.
- ✅ `test_standard --hors-ligne` : groupe 21/21, bis 22/22.
- ⏳ Tests avec le vrai Gemini sur le PC : à lancer avant la fusion dans `main`.

## Suite prévue
Pull Request `atelier-2026-11-24-custodian` → `main` ; documentation complète (fiches de poste avec le Data Custodian,
agent DPO, croisements séparés, workflows et BPMN, schémas, vidéos, guides 2.1 et 2.2, doc de reprise).
