"""Mécanique commune des lanceurs (plomberie, aucune règle métier).

Chaque standard a son propre lancer.py qui déclare SES agents dans l'ordre de SON circuit,
puis appelle executer(). Options en ligne de commande :
    --reprise          relancer sans remettre la base à zéro (les décisions déjà prises sont conservées)
    --domaine NOM      limiter à un domaine (ex. "Supply Chain")
    --bo NOM           limiter à un Business Object (ex. "Lot de production") ; économise le quota Gemini
"""
import argparse
from collections import Counter
from datetime import datetime

import pandas as pd

import commun.outils as o
from commun.creer_base import initialiser
from commun.generer_donnees import generer


def lire_options(standard):
    p = argparse.ArgumentParser(description=f"Lanceur du standard {standard}")
    p.add_argument("--reprise", action="store_true", help="ne pas remettre la base à zéro")
    p.add_argument("--domaine", help="limiter à un domaine")
    p.add_argument("--bo", help="limiter à un Business Object")
    return p.parse_args()


def preparer(reprise):
    """Données et base du standard actif. Avec --reprise, la base existante est conservée."""
    if reprise:
        if not o.BASE.exists():
            raise SystemExit(f"--reprise impossible : la base {o.BASE} n'existe pas encore. Lancez d'abord sans --reprise.")
        print(f"Reprise sur la base existante : {o.BASE.relative_to(o.RACINE)}")
        return
    if not (o.chemin("donnees") / "glossaire_metier.xlsx").exists():
        termes, colonnes = generer()
        print(f"Données générées : {termes} éléments de glossaire, {colonnes} colonnes techniques.")
    print(f"Base créée : {o.BASE.relative_to(o.RACINE)} ({initialiser()} fiches au statut Identifié)")


def perimetre(domaine, bo):
    """Liste des (domaine, [business objects]) à traiter, d'après le registre et le glossaire."""
    domaines = pd.read_excel(o.REGISTRE, dtype=str)["domaine"].tolist()
    if bo and not domaine:
        domaine = next((f["domaine"] for f in o.lire_fiches(chemin="B", business_object=bo)), None)
        if domaine is None:
            raise SystemExit(f"Business Object inconnu : {bo}")
    if domaine:
        if domaine not in domaines:
            raise SystemExit(f"Domaine absent du registre du standard {o.STANDARD} : {domaine}")
        domaines = [domaine]
    resultat = []
    for d in domaines:
        bos = [bo] if bo else sorted({f["business_object"] for f in o.lire_fiches(domaine=d, chemin="B")})
        resultat.append((d, bos))
    return resultat


def ecrire_bilan(domaines):
    """Bilan par domaine : nombre de fiches par statut et par acteur suivant ; écrit dans rapports/bilan.txt."""
    lignes = [f"Bilan du standard {o.STANDARD} — {datetime.now():%d/%m/%Y %H:%M}", ""]
    for d in domaines:
        fiches = o.lire_fiches(domaine=d)
        lignes.append(f"== {d} ({len(fiches)} fiches) ==")
        lignes.append("Par statut : " + ", ".join(f"{s} {n}" for s, n in Counter(f["statut"] for f in fiches).most_common()))
        lignes.append("Qui doit agir :")
        for a, n in Counter(f["acteur_suivant"] or "—" for f in fiches).most_common():
            lignes.append(f"  - {a} : {n}")
        lignes.append("")
    texte = "\n".join(lignes)
    dossier = o.chemin("rapports")
    dossier.mkdir(exist_ok=True)
    (dossier / "bilan.txt").write_text(texte, encoding="utf-8")
    print("\n" + texte + f"\nBilan écrit dans {(dossier / 'bilan.txt').relative_to(o.RACINE)}")


def executer(standard, etapes_par_bo, etapes_par_domaine):
    """Fait tourner le circuit du standard, tour après tour, tant qu'il reste des fiches « À corriger »."""
    options = lire_options(standard)
    print(f"=== Lanceur du standard {standard} ===")
    preparer(options.reprise)
    cibles = perimetre(options.domaine, options.bo)
    max_tours = o.charger_regles()["max_allers_retours"] + 1

    for tour in range(1, max_tours + 1):
        print(f"\n--- Tour {tour} ---")
        for domaine, bos in cibles:
            for bo in bos:
                for etape in etapes_par_bo:
                    etape(domaine, bo)
            for etape in etapes_par_domaine:
                etape(domaine)
        a_corriger = [f for d, _ in cibles for f in o.lire_fiches(domaine=d, statut="À corriger")]
        if not a_corriger:
            print(f"\nAucune fiche « À corriger » après le tour {tour} : circuit terminé.")
            break
        print(f"\n{len(a_corriger)} fiche(s) « À corriger » : nouveau tour.")

    ecrire_bilan([d for d, _ in cibles])
