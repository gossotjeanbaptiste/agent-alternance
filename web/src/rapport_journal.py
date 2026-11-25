"""Rapport : ce que les journaux du jour (logs/AAAA-MM-JJ.log) disent de l'activité sur une période.

Chaque routine commence par « ===== ROUTINE ALTERNANCE (…) ===== » ; une routine lancée en essai
(« essai » dans l'en-tête, ou lignes « [essai] ») n'est pas comptée : elle n'a rien écrit.
"""
import re
from collections import Counter
from datetime import date

from chemins import LOGS

HEURE = re.compile(r"^\[\d\d:\d\d:\d\d\]\s?")
FICHIER = re.compile(r"^(\d{4})-(\d\d)-(\d\d)\.log$")
TERMINEE = re.compile(r"✅ Routine(?: « ([^»]+) »)? terminée en (\d+) min")
TYPE_REPONSE = re.compile(r"📩 .*?: réponse \[([^\]]+)\]")
MACHINE = re.compile(r"🧠 Modèle utilisé : ([^(]+)")
NB_PROBLEMES = 12


def fichiers(debut, fin):
    """Journaux du jour compris entre debut et fin (dates incluses), du plus ancien au plus récent."""
    if not LOGS.exists():
        return []
    trouves = []
    for f in LOGS.glob("*.log"):
        m = FICHIER.match(f.name)
        if m:
            jour = date(*map(int, m.groups()))
            if debut <= jour <= fin:
                trouves.append((jour, f))
    return sorted(trouves)


def sections(texte):
    """Découpe un journal en blocs (une routine par bloc ; le premier bloc = ce qui précède)."""
    blocs, courant = [], []
    for ligne in texte.splitlines():
        ligne = HEURE.sub("", ligne).strip()
        if ligne.startswith("=====") and courant:
            blocs.append(courant)
            courant = []
        if ligne:
            courant.append(ligne)
    if courant:
        blocs.append(courant)
    return blocs


def est_essai(bloc):
    return ("essai" in bloc[0] and bloc[0].startswith("=====")) or any(l.startswith("[essai]") for l in bloc)


def vide():
    return {"jours": 0, "routines": Counter(), "minutes": 0, "candidatures": 0, "lettres": 0,
            "relances_brouillon": 0, "envois_vus": 0, "relances_vues": 0,
            "reponses": Counter(), "machines": Counter(), "problemes": [], "essais": 0}


def compter_ligne(r, l):
    """Ajoute au résumé r ce que dit une ligne du journal."""
    if (m := TERMINEE.search(l)):
        r["routines"][m.group(1) or "routine"] += 1
        r["minutes"] += int(m.group(2))
    elif l.startswith("📝"):
        if ": relance" in l:
            r["relances_brouillon"] += 1
        elif "lettre prête" in l:
            r["lettres"] += 1
        else:
            r["candidatures"] += 1
    elif l.startswith("✉️"):
        r["envois_vus"] += 1
    elif l.startswith("🔁"):
        r["relances_vues"] += 1
    elif (m := TYPE_REPONSE.search(l)):
        r["reponses"][m.group(1)] += 1
    elif (m := MACHINE.search(l)):
        r["machines"][m.group(1).strip()] += 1
    elif l.startswith(("⚠️", "❌")) and l not in r["problemes"] and len(r["problemes"]) < NB_PROBLEMES:
        r["problemes"].append(l)


def resumer(debut, fin):
    """Résumé de l'activité notée dans les journaux entre debut et fin."""
    r = vide()
    for _jour, f in fichiers(debut, fin):
        r["jours"] += 1
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for bloc in sections(texte):
            if est_essai(bloc):
                r["essais"] += 1
                continue
            for l in bloc:
                compter_ligne(r, l)
    return r
