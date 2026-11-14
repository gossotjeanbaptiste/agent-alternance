"""Page « Écartées » : entreprises refusées par le filtre d'activité, avec la raison, un lien vers leur site
(ou une recherche Google), et les décisions « Candidater quand même », « Abandonner », « Remettre »."""
from datetime import date

import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
import lettres
import refus
import routines
from tableau import COLS_A_CONTACTER, Suivi, norm


def _site(adresse):
    adresse = str(adresse or "").strip()
    if adresse and not adresse.lower().startswith(("http://", "https://")):
        adresse = "https://" + adresse
    return adresse


def lire():
    """{"a_examiner": [...], "demandees": [...], "abandonnees": [...]} : lignes du fichier, avec _cle, _raison,
    _site et _recherche (recherche Google sur le nom et la ville)."""
    groupes = {"a_examiner": [], "demandees": [], "abandonnees": []}
    for l in refus.lire().values():
        site, recherche = lettres.site_ou_recherche({"Entreprise": l["Entreprise"], "Lieu": l["Adresse"]})
        l = {**l, "_cle": refus.cle(l), "_raison": refus.raison(l), "_site": _site(l.get("Site")) or site,
             "_recherche": recherche}
        decision = l.get("Décision") or ""
        if decision == refus.ABANDONNEE:
            groupes["abandonnees"].append(l)
        elif decision.startswith(refus.DEMANDEE):
            groupes["demandees"].append(l)
        else:
            groupes["a_examiner"].append(l)
    for g in groupes.values():
        g.sort(key=lambda l: (l["Entreprise"] or "").lower())
    return groupes


def _infos(l):
    morceaux = [f"Activité : {l['Activité']}" if l.get("Activité") else "",
                f"SIRET {l['SIRET']}" if l.get("SIRET") else "",
                "Écartée par le filtre d'activité, candidature demandée quand même"]
    return " | ".join(m for m in morceaux if m)


def candidater(identifiant):
    """Ajoute l'entreprise à la feuille « À contacter » du tableau (traitée en premier à la prochaine recherche)
    et note la décision. Renvoie (ok, message)."""
    if routines.en_cours():
        return False, "Une routine est en cours : attends qu'elle se termine pour modifier le tableau."
    l = refus.lire().get(identifiant)
    if l is None:
        return False, "Entreprise introuvable dans la liste (elle a changé) : recharge la page."
    s = Suivi(commun.chemin_tableau())
    nom = norm(l["Entreprise"])
    if any(norm(s.get(r, "Entreprise")) == nom for r in s.rows()):
        return False, f"{l['Entreprise']} est déjà dans le tableau de suivi."
    if s.ac is None:
        s.ac = s.wb.create_sheet("À contacter")
    entetes = {c.value: i for i, c in enumerate(s.ac[1]) if c.value}
    for col in COLS_A_CONTACTER:          # colonnes manquantes (ancien tableau, feuille vide)
        if col not in entetes:
            entetes[col] = len(entetes)
            s.ac.cell(1, entetes[col] + 1, col)
    for r in s.ac.iter_rows(min_row=2):
        i = entetes["Entreprise"]
        if i < len(r) and norm(r[i].value) == nom and not r[entetes["Traité"]].value:
            return False, f"{l['Entreprise']} est déjà dans la feuille « À contacter »."
    valeurs = {"Entreprise": l["Entreprise"], "Poste": "Candidature spontanée", "Lieu": l["Adresse"],
               "Infos": _infos(l), "Site": _site(l.get("Site"))}
    ligne = s.ac.max_row + 1
    for col, v in valeurs.items():
        s.ac.cell(ligne, entetes[col] + 1, v)
    s.mise_en_forme()
    try:
        s.wb.save(s.path)
    except PermissionError:
        return False, "Le tableau est ouvert dans Excel : ferme-le puis réessaie."
    ok, message = refus.decider(identifiant, f"{refus.DEMANDEE} le {date.today():%d/%m/%Y}")
    if not ok:
        return False, f"Ajoutée à « À contacter », mais décision non notée : {message}"
    return True, (f"{l['Entreprise']} ajoutée à la feuille « À contacter » : sa candidature sera écrite "
                  "à la prochaine recherche de nouvelles entreprises.")


def abandonner(identifiant):
    return refus.decider(identifiant, refus.ABANDONNEE)


def remettre(identifiant):
    """Remet une entreprise abandonnée dans la liste à examiner."""
    return refus.decider(identifiant, "")


ACTIONS = {"candidater": candidater, "abandonner": abandonner, "remettre": remettre}
