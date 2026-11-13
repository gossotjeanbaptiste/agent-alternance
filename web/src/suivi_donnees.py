"""Lecture du tableau de suivi, statistiques du tableau de bord et modification d'une ligne."""
from collections import Counter
from datetime import date, timedelta

import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
import routines
from commun import CFG, P
from tableau import A_POSTULER, Suivi, as_date

REPONDU = {"Réponse positive", "Entretien", "Accepté", "Refus", "Réponse à lire"}
EN_ATTENTE = {"Candidaté (mail)", "Relancé", "Relance en brouillon", "Relance programmée",
              "Candidaté (La Bonne Alternance)", "Candidaté (formulaire du site)", "Candidaté (LinkedIn)",
              "Candidaté (autre canal)"}
COLONNES_DATES = ("Date ajout", "Date envoi", "Dernière action", "Relance prévue")


def lire():
    """Toutes les lignes du tableau, sous forme de dictionnaires (avec leur numéro de ligne Excel)."""
    s = Suivi(commun.chemin_tableau())
    lignes = []
    for r in s.rows():
        d = {c: s.get(r, c) for c in s.h}
        d["_ligne"] = r[0].row
        for c in COLONNES_DATES:
            d[c] = as_date(d.get(c))
        lignes.append(d)
    return lignes


def statistiques(lignes):
    aujourd_hui = date.today()
    st = Counter(l.get("Statut") or "?" for l in lignes)
    envoyees = [l for l in lignes if l.get("Date envoi")]
    reponses = [l for l in envoyees if l.get("Statut") in REPONDU]
    lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    semaines = []
    for i in range(9, -1, -1):
        debut = lundi - timedelta(weeks=i)
        n = sum(1 for l in envoyees if debut <= l["Date envoi"] < debut + timedelta(days=7))
        semaines.append({"libelle": f"{debut:%d/%m}", "n": n})
    relances = sorted((l for l in lignes if l.get("Statut") in {"Candidaté (mail)", "Relancé"} and l.get("Relance prévue")),
                      key=lambda l: l["Relance prévue"])[:8]
    return {
        "envoyees": len(envoyees),
        "semaine": sum(1 for l in envoyees if l["Date envoi"] >= aujourd_hui - timedelta(days=7)),
        "reponses": len(reponses),
        "taux": round(100 * len(reponses) / len(envoyees)) if envoyees else 0,
        "entretiens": st.get("Entretien", 0) + st.get("Accepté", 0),
        "en_cours": sum(st.get(k, 0) for k in EN_ATTENTE),
        "a_postuler": sum(st.get(k, 0) for k in A_POSTULER),
        "par_statut": sorted(st.items(), key=lambda x: -x[1]),
        "semaines": semaines,
        "maxi": max([w["n"] for w in semaines] + [1]),
        "relances": relances,
    }


def modifier(n_ligne, entreprise, champs):
    """Modifie une ligne (après avoir vérifié que c'est bien la bonne entreprise). Renvoie (ok, message)."""
    if routines.en_cours():
        return False, "Une routine est en cours : attends qu'elle se termine pour modifier le tableau."
    s = Suivi(commun.chemin_tableau())
    row = next((r for r in s.rows() if r[0].row == n_ligne), None)
    if not row or str(s.get(row, "Entreprise")) != entreprise:
        return False, "Ligne introuvable (le tableau a changé) : recharge la page."
    for k, v in champs.items():
        s.set(row, k, v)
    s.mise_en_forme()
    try:
        s.wb.save(s.path)
    except PermissionError:
        return False, "Le tableau est ouvert dans Excel : ferme-le puis réessaie."
    return True, "Enregistré."
