"""Routines lancées tous les jours par le Planificateur de tâches Windows (schtasks).

Chaque tâche s'appelle « LMAgent_<routine> » et lance lmagent --routine <routine> (l'exe dans la version
installée, python lmagent.py depuis le code). Le PC doit être allumé et la session ouverte à l'heure prévue.
"""
import csv
import io
import re
import subprocess

PREFIXE = "LMAgent_"
ROUTINES = ("relances", "recherche", "tout")
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, errors="replace",
                          creationflags=SANS_FENETRE)


def taches():
    """{routine: {"prochaine": "…", "etat": "…"}} des routines planifiées."""
    res = {}
    for nom in ROUTINES:
        r = _schtasks("/Query", "/TN", PREFIXE + nom, "/FO", "CSV", "/NH")
        if r.returncode != 0 or not r.stdout.strip():
            continue
        ligne = next(csv.reader(io.StringIO(r.stdout.strip().splitlines()[-1])), [])
        if len(ligne) >= 3:
            res[nom] = {"prochaine": ligne[1], "etat": ligne[2]}
    return res


def planifier(nom, heure):
    """Crée (ou remplace) la tâche quotidienne. Renvoie (ok, message)."""
    import lmagent
    if nom not in ROUTINES:
        return False, "Routine inconnue."
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", heure or ""):
        return False, "Heure au format HH:MM attendue (ex. 10:00)."
    commande = subprocess.list2cmdline(lmagent.commande_soi() + ["--routine", nom])
    r = _schtasks("/Create", "/TN", PREFIXE + nom, "/TR", commande, "/SC", "DAILY", "/ST", heure, "/F")
    if r.returncode != 0:
        return False, f"Planification impossible : {(r.stderr or r.stdout).strip()}"
    return True, f"« {nom} » planifiée tous les jours à {heure}."


def supprimer(nom):
    if nom not in ROUTINES:
        return False, "Routine inconnue."
    r = _schtasks("/Delete", "/TN", PREFIXE + nom, "/F")
    if r.returncode != 0:
        return False, f"Suppression impossible : {(r.stderr or r.stdout).strip()}"
    return True, f"« {nom} » n'est plus planifiée."
