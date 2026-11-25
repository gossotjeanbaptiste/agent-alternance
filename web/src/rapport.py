"""Page Rapport : bilan des recherches sur une période, d'après le tableau de suivi et les journaux.

    periode(args)     dates choisies (7, 30, 90 derniers jours, tout, ou du … au …)
    generer(args)     le rapport complet (tableau, journaux, entreprises écartées) affiché par rapport.html
    texte(r)          le même rapport en texte simple, à copier dans un mail ou un document
"""
from datetime import date, timedelta

import rapport_journal
import rapport_tableau
import suivi_donnees

PERIODES = [("7", "7 derniers jours"), ("30", "30 derniers jours"), ("90", "90 derniers jours"), ("0", "Depuis le début")]
DEBUT_DE_TOUT = date(2000, 1, 1)


def _date(texte):
    try:
        return date.fromisoformat(str(texte or "").strip())
    except ValueError:
        return None


def periode(args):
    """(debut, fin, cle) : du … au … si les deux dates sont valides, sinon les N derniers jours (30 par défaut)."""
    aujourd_hui = date.today()
    du, au = _date(args.get("du")), _date(args.get("au"))
    if du and au:
        return (min(du, au), max(du, au), "dates")
    jours = str(args.get("jours") or "30")
    if jours not in dict(PERIODES):
        jours = "30"
    if jours == "0":
        return DEBUT_DE_TOUT, aujourd_hui, "0"
    return aujourd_hui - timedelta(days=int(jours) - 1), aujourd_hui, jours


def ecartees(debut, fin):
    """Entreprises écartées par le filtre d'activité pour la première fois entre debut et fin (sans doublon :
    les journaux, eux, la notent à chaque recherche)."""
    import refus
    n = 0
    for l in refus.lire().values():
        try:
            j, m, a = (int(x) for x in str(l.get("Première fois") or "").split("/"))
            n += debut <= date(a, m, j) <= fin
        except ValueError:
            continue
    return n


def generer(args, lignes=None):
    debut, fin, cle = periode(args)
    lignes = suivi_donnees.lire() if lignes is None else lignes
    if cle == "0":   # « depuis le début » : première date connue du tableau
        dates = [l.get(c) for l in lignes for c in ("Date ajout", "Date envoi") if l.get(c)]
        debut = min(dates) if dates else fin
    return {"debut": debut, "fin": fin, "cle": cle, "genere": date.today(),
            "t": rapport_tableau.resumer(lignes, debut, fin), "j": rapport_journal.resumer(debut, fin),
            "ecartees": ecartees(debut, fin), "lignes": lignes}


def _liste(paires):
    return ", ".join(f"{k} : {n}" for k, n in paires) or "aucune"


def texte(r):
    """Le rapport en texte simple (sans couleur ni tableau), à coller où on veut."""
    t, j = r["t"], r["j"]
    lignes = [f"Bilan de ma recherche d'alternance du {r['debut']:%d/%m/%Y} au {r['fin']:%d/%m/%Y}", "",
              f"- Candidatures envoyées : {t['envoyees']} ({_liste(t['par_canal'])})",
              f"- Réponses reçues : {t['reponses']} ({_liste(t['par_reponse'])})",
              f"- Entretiens ou réponses positives : {t['entretiens']}",
              f"- Taux de réponse des candidatures de la période : {t['taux']} %",
              f"- Entreprises ajoutées au suivi : {t['ajoutees']}",
              f"- Relances : {j['relances_brouillon']} préparée(s), {j['relances_vues']} envoyée(s) repérée(s)",
              f"- Entreprises écartées (hors informatique) : {r['ecartees']}",
              f"- Routines automatiques terminées : {sum(j['routines'].values())}", "",
              f"Aujourd'hui : {t['total']} entreprises suivies, {t['en_attente']} candidatures en attente de réponse, "
              f"{t['a_postuler']} à postuler, {t['total_entretiens']} entretien(s) ou réponse(s) positive(s)."]
    if t["liste_envoyees"]:
        lignes += ["", "Candidatures envoyées :"]
        for l in t["liste_envoyees"]:
            poste = f" — {l['Poste']}" if l.get("Poste") else ""
            lieu = f" ({l['Lieu']})" if l.get("Lieu") else ""
            lignes.append(f"  {l['Date envoi']:%d/%m} {l.get('Entreprise') or '?'}{poste}{lieu} : {l.get('Statut') or ''}")
    if t["liste_reponses"]:
        lignes += ["", "Réponses :"]
        for l in t["liste_reponses"]:
            lignes.append(f"  {l.get('Entreprise') or '?'} : {l.get('Statut')}")
    return "\n".join(lignes)
