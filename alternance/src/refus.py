"""Liste des entreprises écartées par le filtre d'activité (codes NAF) de La Bonne Alternance.

Tenue à jour à chaque passage de la recherche dans alternance/donnees/entreprises_refusees.csv
(non versionné ; s'ouvre dans Excel) : une ligne par entreprise (SIRET), avec son activité,
la première et la dernière fois qu'elle a été écartée, et le nombre de passages.
"""
import csv
from datetime import date

import commun
import donnees

FICHIER = donnees.chemin("entreprises_refusees.csv")
COLS = ["Entreprise", "SIRET", "Code NAF", "Activité", "Adresse", "Recherche",
        "Première fois", "Dernière fois", "Passages"]


def lire():
    try:
        with open(FICHIER, encoding="utf-8-sig", newline="") as f:
            return {l["SIRET"] or l["Entreprise"]: l for l in csv.DictReader(f, delimiter=";")}
    except FileNotFoundError:
        return {}


def noter(ecartees):
    """Ajoute / met à jour les entreprises écartées : [{"Entreprise", "SIRET", "Code NAF", "Activité",
    "Adresse", "Recherche"}]. Rien n'est écrit en mode essai, ni si le fichier est ouvert dans Excel."""
    if commun.ESSAI or not ecartees:
        return
    tout = lire()
    aujourd_hui = f"{date.today():%d/%m/%Y}"
    for e in ecartees:
        cle = e.get("SIRET") or e["Entreprise"]
        l = tout.get(cle)
        if l is None:
            tout[cle] = {**{c: "" for c in COLS}, **e, "Première fois": aujourd_hui,
                         "Dernière fois": aujourd_hui, "Passages": "1"}
        elif l["Dernière fois"] != aujourd_hui:  # compté une fois par jour (plusieurs villes, plusieurs lancements)
            l.update({**e, "Dernière fois": aujourd_hui, "Passages": str(int(l.get("Passages") or 0) + 1)})
    lignes = sorted(tout.values(), key=lambda l: (l["Activité"].lower(), l["Entreprise"].lower()))
    try:
        with open(FICHIER, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(lignes)
    except PermissionError:
        commun.say(f"   ⚠️ {FICHIER.name} est ouvert (Excel ?) : liste des entreprises écartées non mise à jour")
