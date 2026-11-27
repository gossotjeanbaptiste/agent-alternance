"""Chiffres du tableau de bord : indicateurs, candidatures envoyées par semaine (numéro de semaine ISO),
candidatures regroupées par étape et envois par canal."""
import re
from collections import Counter
from datetime import date, timedelta

from suivi_donnees import EN_ATTENTE, REPONDU
from tableau import PAGE_A_POSTULER

SEMAINES = 16          # semaines affichées dans le graphique
ENTRETIENS = {"Entretien", "Demande de disponibilités", "Accepté", "Réponse positive"}
# étapes du graphique « Où en sont tes candidatures » : (nom, statuts) ; ce qui n'est nulle part va dans la dernière
ETAPES = [
    ("À postuler", set(PAGE_A_POSTULER)),
    ("En attente de réponse", EN_ATTENTE),
    ("Entretiens et réponses positives", ENTRETIENS),
    ("Autres réponses", {"Réponse à lire", "Candidature transmise"}),
    ("Refus", {"Refus"}),
    ("Sans suite", set()),       # sans réponse, abandonnées, adresses invalides…
]


def a_repondu(l):
    """L'entreprise a répondu : statut de réponse, ou vraie réponse notée (« Dernière réponse » sans [automatique]),
    même si la ligne est passée ensuite à « Abandonné » ou « Sans réponse »."""
    if l.get("Statut") in REPONDU:
        return True
    m = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} \[(\w+)\]", str(l.get("Dernière réponse") or ""))
    return bool(m) and m.group(1) != "automatique"


def canal(statut):
    """« Candidaté (LinkedIn) » → « LinkedIn » ; les candidatures relancées ou à réponse viennent d'un mail."""
    s = statut or ""
    if s.startswith("Candidaté (") and s.endswith(")"):
        return s[len("Candidaté ("):-1]
    return "mail"


def libelle_semaine(jour):
    """Semaine ISO du jour : (« Semaine 47 », « 2026 »). L'année est celle de la semaine ISO : le 01/01/2027 est
    dans la semaine 53 de 2026."""
    annee, semaine, _ = jour.isocalendar()
    return f"Semaine {semaine}", str(annee)


def par_semaine(envoyees, aujourd_hui, n=SEMAINES):
    lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    res = []
    for i in range(n - 1, -1, -1):
        debut = lundi - timedelta(weeks=i)
        nb = sum(1 for l in envoyees if debut <= l["Date envoi"] < debut + timedelta(days=7))
        semaine, annee = libelle_semaine(debut)
        res.append({"semaine": semaine, "annee": annee, "n": nb, "du": debut, "au": debut + timedelta(days=6)})
    return res


def etapes(lignes):
    """[{num (couleur), nom, n, part (%), statuts: [(statut, n)]}] dans l'ordre d'ETAPES (étapes vides comprises)."""
    groupes = {nom: Counter() for nom, _ in ETAPES}
    for l in lignes:
        st = l.get("Statut") or "?"
        nom = next((nom for nom, statuts in ETAPES if st in statuts), ETAPES[-1][0])
        groupes[nom][st] += 1
    total = max(1, len(lignes))
    return [{"num": i + 1, "nom": nom, "n": sum(c.values()), "part": round(100 * sum(c.values()) / total, 1),
             "statuts": c.most_common()} for i, (nom, c) in enumerate(groupes.items())]


def calculer(lignes, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    envoyees = [l for l in lignes if l.get("Date envoi")]
    repondues = [l for l in envoyees if a_repondu(l)]
    semaines = par_semaine(envoyees, aujourd_hui)
    canaux = Counter(canal(l.get("Statut")) for l in envoyees).most_common()
    dans_7_jours = aujourd_hui + timedelta(days=7)
    relances = [l for l in lignes if l.get("Statut") in {"Candidaté (mail)", "Relancé"}
                and l.get("Relance prévue") and l["Relance prévue"] <= dans_7_jours]
    return {
        "envoyees": len(envoyees),
        "cette_semaine": semaines[-1]["n"],
        "semaine_derniere": semaines[-2]["n"],
        "semaine": semaines[-1]["semaine"],
        "reponses": len(repondues),
        "taux": round(100 * len(repondues) / len(envoyees)) if envoyees else 0,
        "entretiens": sum(1 for l in lignes if l.get("Statut") in ENTRETIENS),
        "en_cours": sum(1 for l in lignes if l.get("Statut") in EN_ATTENTE),
        "a_postuler": sum(1 for l in lignes if l.get("Statut") in PAGE_A_POSTULER),   # = cartes de « À postuler »
        "relances_7j": len(relances),
        "semaines": semaines,
        "maxi": max([w["n"] for w in semaines] + [1]),
        "moyenne": round(sum(w["n"] for w in semaines) / len(semaines), 1),
        "etapes": etapes(lignes),
        "total": len(lignes),
        "canaux": canaux,
        "maxi_canal": max([n for _, n in canaux] + [1]),
    }
