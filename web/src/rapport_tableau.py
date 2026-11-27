"""Rapport : ce que le tableau de suivi dit des candidatures sur une période."""
from collections import Counter
from datetime import date, timedelta

from suivi_donnees import EN_ATTENTE, REPONDU
from tableau import PAGE_A_POSTULER

ENTRETIENS = {"Entretien", "Demande de disponibilités", "Accepté", "Réponse positive"}
JOURS_RELANCES = 14


def dans(d, debut, fin):
    return d is not None and debut <= d <= fin


def canal(statut):
    """« Candidaté (mail) » → « mail » ; les autres statuts envoyés comptent comme « mail »."""
    s = statut or ""
    if s.startswith("Candidaté (") and s.endswith(")"):
        return s[len("Candidaté ("):-1]
    return "mail"


def resumer(lignes, debut, fin):
    """Résumé du tableau entre debut et fin (dates incluses)."""
    envoyees = [l for l in lignes if dans(l.get("Date envoi"), debut, fin)]
    envoyees.sort(key=lambda l: l["Date envoi"], reverse=True)
    reponses = [l for l in lignes if l.get("Statut") in REPONDU
                and dans(l.get("Dernière action") or l.get("Date envoi"), debut, fin)]
    reponses.sort(key=lambda l: l.get("Dernière action") or l.get("Date envoi"), reverse=True)
    st_reponses = Counter(l.get("Statut") for l in reponses)
    from statistiques import a_repondu    # même définition que le tableau de bord
    repondues_parmi = sum(1 for l in envoyees if a_repondu(l))
    aujourd_hui = date.today()
    relances = sorted((l for l in lignes if l.get("Statut") in {"Candidaté (mail)", "Relancé"}
                       and dans(l.get("Relance prévue"), aujourd_hui, aujourd_hui + timedelta(days=JOURS_RELANCES))),
                      key=lambda l: l["Relance prévue"])
    return {
        "ajoutees": sum(1 for l in lignes if dans(l.get("Date ajout"), debut, fin)),
        "envoyees": len(envoyees),
        "par_canal": Counter(canal(l.get("Statut")) for l in envoyees).most_common(),
        "par_source": Counter((l.get("Source") or "?").split(" (")[0] for l in envoyees).most_common(),
        "reponses": len(reponses),
        "par_reponse": st_reponses.most_common(),
        "entretiens": sum(n for s, n in st_reponses.items() if s in ENTRETIENS),
        "refus": st_reponses.get("Refus", 0),
        "taux": round(100 * repondues_parmi / len(envoyees)) if envoyees else 0,
        "liste_envoyees": envoyees,
        "liste_reponses": reponses,
        "relances": relances,
        "total": len(lignes),
        "en_attente": sum(1 for l in lignes if l.get("Statut") in EN_ATTENTE),
        "a_postuler": sum(1 for l in lignes if l.get("Statut") in PAGE_A_POSTULER),
        "total_entretiens": sum(1 for l in lignes if l.get("Statut") in ENTRETIENS),
    }
