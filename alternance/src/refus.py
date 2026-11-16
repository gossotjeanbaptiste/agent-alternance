"""Liste des entreprises écartées par le filtre d'activité (codes NAF) de La Bonne Alternance.

Tenue à jour à chaque passage de la recherche dans donnees/entreprises_refusees.csv (non versionné ; s'ouvre
dans Excel) : une ligne par entreprise (SIRET), avec son activité, la raison de l'écart, la première et la dernière
fois qu'elle a été écartée, le nombre de passages et la décision prise dans l'interface (page « Écartées ») :
vide (à examiner), « Abandonnée » ou « Candidature demandée le JJ/MM/AAAA ».
"""
import csv
from datetime import date

import commun
import donnees

FICHIER = donnees.chemin("entreprises_refusees.csv")
COLS = ["Entreprise", "SIRET", "Code NAF", "Activité", "Adresse", "Site", "Recherche", "Raison",
        "Première fois", "Dernière fois", "Passages", "Décision"]
ABANDONNEE = "Abandonnée"
DEMANDEE = "Candidature demandée"
FAITE = "Candidature faite"     # la candidature demandée a été écrite (entreprise présente dans le suivi)


def cle(l):
    """Identifiant d'une entreprise de la liste : son SIRET, sinon son nom."""
    return l.get("SIRET") or l.get("Entreprise") or ""


def raison(l):
    """Pourquoi l'entreprise a été écartée (colonne « Raison », sinon déduite de l'activité)."""
    if l.get("Raison"):
        return l["Raison"]
    code = f" ({l['Code NAF']})" if l.get("Code NAF") else ""
    return f"Activité hors informatique : {l.get('Activité') or 'inconnue'}{code}"


def lire():
    try:
        with open(FICHIER, encoding="utf-8-sig", newline="") as f:
            return {cle(l): {c: l.get(c) or "" for c in COLS} for l in csv.DictReader(f, delimiter=";")}
    except FileNotFoundError:
        return {}


def ecrire(tout):
    """Réécrit le fichier (trié par activité puis nom). Lève PermissionError s'il est ouvert dans Excel."""
    lignes = sorted(tout.values(), key=lambda l: (l["Activité"].lower(), l["Entreprise"].lower()))
    with open(FICHIER, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=";", extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(lignes)


def noter(ecartees):
    """Ajoute / met à jour les entreprises écartées : [{"Entreprise", "SIRET", "Code NAF", "Activité",
    "Adresse", "Site", "Recherche", "Raison"}]. La décision déjà prise est gardée.
    Rien n'est écrit en mode essai, ni si le fichier est ouvert dans Excel."""
    if commun.ESSAI or not ecartees:
        return
    tout = lire()
    aujourd_hui = f"{date.today():%d/%m/%Y}"
    for e in ecartees:
        l = tout.get(cle(e))
        if l is None:
            tout[cle(e)] = {**{c: "" for c in COLS}, **e, "Première fois": aujourd_hui,
                            "Dernière fois": aujourd_hui, "Passages": "1"}
        elif l["Dernière fois"] != aujourd_hui:  # compté une fois par jour (plusieurs villes, plusieurs lancements)
            l.update({**{k: v for k, v in e.items() if v}, "Dernière fois": aujourd_hui,
                      "Passages": str(int(l.get("Passages") or 0) + 1)})
    try:
        ecrire(tout)
    except PermissionError:
        commun.say(f"   ⚠️ {FICHIER.name} est ouvert (Excel ?) : liste des entreprises écartées non mise à jour")


def decider(identifiant, decision):
    """Note la décision (« Abandonnée », « Candidature demandée le … » ou "" pour remettre). Renvoie (ok, message)."""
    tout = lire()
    if identifiant not in tout:
        return False, "Entreprise introuvable dans la liste (elle a changé) : recharge la page."
    tout[identifiant]["Décision"] = decision
    try:
        ecrire(tout)
    except PermissionError:
        return False, f"{FICHIER.name} est ouvert dans Excel : ferme-le puis réessaie."
    return True, "Enregistré."
