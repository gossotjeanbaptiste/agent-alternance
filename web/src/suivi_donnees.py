"""Lecture du tableau de suivi, statistiques du tableau de bord et modification d'une ligne."""
from collections import Counter
from datetime import date, timedelta

import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
import routines
from commun import CFG, P
from tableau import PAGE_A_POSTULER, Suivi, as_date

REPONDU = {"Réponse positive", "Entretien", "Accepté", "Refus", "Réponse à lire", "Candidature transmise"}
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
        "a_postuler": sum(st.get(k, 0) for k in PAGE_A_POSTULER),   # même chose que la page « À postuler »
        "par_statut": sorted(st.items(), key=lambda x: -x[1]),
        "semaines": semaines,
        "maxi": max([w["n"] for w in semaines] + [1]),
        "relances": relances,
    }


CHAMPS_AJOUT = ("Entreprise", "Poste", "Lieu", "Contact", "Email", "Téléphone", "Lien", "Source", "Notes")


def ajouter(d):
    """Ajoute une candidature saisie dans la page Suivi. d : champs du formulaire + "Statut", "Date envoi"
    (AAAA-MM-JJ, facultative) et "forcer" (ajouter même si l'entreprise semble déjà dans le tableau).
    Renvoie (ok, message, doublon)."""
    import re
    from mails import est_adresse
    from tableau import STATUTS, deja_contactee
    vals = {c: str(d.get(c) or "").strip() for c in CHAMPS_AJOUT}
    if not vals["Entreprise"]:
        return False, "Indique au moins le nom de l'entreprise.", False
    statut = str(d.get("Statut") or "").strip()
    if statut not in STATUTS:
        return False, "Statut inconnu.", False
    if vals["Email"] and not est_adresse(vals["Email"]):
        return False, f"Adresse mail invalide : {vals['Email']}", False
    envoi = None
    if d.get("Date envoi"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d["Date envoi"])):
            return False, "Date d'envoi invalide.", False
        envoi = date.fromisoformat(str(d["Date envoi"]))
    if routines.en_cours():
        return False, "Une routine est en cours : attends qu'elle se termine pour modifier le tableau.", False
    s = Suivi(commun.chemin_tableau())
    o = {"entreprise": vals["Entreprise"], "lieu": vals["Lieu"], "email": vals["Email"]}
    if not d.get("forcer") and deja_contactee(o, *s.deja_vus()):
        return False, (f"{vals['Entreprise']} semble déjà dans le tableau (même nom dans la même ville, ou même "
                       "adresse mail)."), True
    aujourd_hui = date.today()
    lignes = {**vals, "Date ajout": aujourd_hui, "Statut": statut, "Nb relances": 0,
              "Source": vals["Source"] or "Ajout manuel"}
    if statut.startswith("Candidaté") or statut in ("Relancé", "Relance programmée"):
        envoi = envoi or aujourd_hui
    if envoi:
        lignes.update({"Date envoi": envoi, "Dernière action": envoi})
        if statut == "Candidaté (mail)":           # suivie et relancée comme une candidature envoyée par le script
            from jours import date_relance
            lignes["Relance prévue"] = date_relance(envoi)
    s.add(**lignes)
    s.mise_en_forme()
    try:
        s.enregistrer_sur()
    except PermissionError:
        return False, "Le tableau est ouvert dans Excel : ferme-le puis réessaie.", False
    return True, f"{vals['Entreprise']} ajoutée au suivi ({statut}).", False


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
        s.enregistrer_sur()
    except PermissionError:
        return False, "Le tableau est ouvert dans Excel : ferme-le puis réessaie."
    return True, "Enregistré."
