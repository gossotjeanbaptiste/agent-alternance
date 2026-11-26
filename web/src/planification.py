"""Routines lancées tous les jours par le Planificateur de tâches Windows (schtasks).

Une tâche par heure de passage : « LMAgent_<routine>_<HHMM> » (ex. LMAgent_recherche_1000), qui lance
lmagent --routine <routine> --fois <passages> (l'exe dans la version installée, python lmagent.py depuis le code).
Une même routine peut donc être planifiée à plusieurs heures, chacune avec son nombre de passages. Les tâches des
versions précédentes (« LMAgent_<routine> », une seule heure) restent affichées et supprimables.
Le PC doit être allumé et la session ouverte à l'heure prévue.
"""
import csv
import io
import re
import subprocess

PREFIXE = "LMAgent_"
ROUTINES = ("relances", "recherche", "tout", "mails", "reponses")
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NOM_TACHE = re.compile(rf"^\\?{PREFIXE}({'|'.join(ROUTINES)})(?:_(\d{{4}}))?$")
HEURE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _encodage():
    """schtasks écrit dans le jeu de caractères de la console (« Prêt » illisible sinon)."""
    import codecs
    try:
        return codecs.lookup("oem").name
    except LookupError:         # hors Windows
        return None


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, encoding=_encodage(),
                          errors="replace", creationflags=SANS_FENETRE)


def _lignes(sortie):
    return [l for l in csv.reader(io.StringIO(sortie or "")) if l]


def nom_tache(routine, heure):
    return f"{PREFIXE}{routine}_{heure.replace(':', '')}"


def taches():
    """[{"id", "routine", "heure", "fois", "prochaine", "etat"}] des routines planifiées, par routine puis heure."""
    r = _schtasks("/Query", "/FO", "CSV", "/NH")
    noms = []
    for l in _lignes(r.stdout if r.returncode == 0 else ""):
        nom = l[0].lstrip("\\")
        if NOM_TACHE.match(nom) and nom not in noms:
            noms.append(nom)
    res = []
    for nom in noms:
        v = _schtasks("/Query", "/TN", nom, "/V", "/FO", "CSV", "/NH")
        l = next(iter(_lignes(v.stdout)), []) if v.returncode == 0 else []
        if len(l) < 9:          # colonnes de /V : hôte, nom, prochaine exécution, état, …, tâche à exécuter (9e)
            continue
        routine, hhmm = NOM_TACHE.match(nom).groups()
        if hhmm:
            heure = f"{hhmm[:2]}:{hhmm[2:]}"
        else:                   # tâche d'une version précédente : l'heure de sa prochaine exécution
            h = re.search(r"\b(\d{1,2}:\d{2})", l[2])
            heure = h.group(1).zfill(5) if h else ""
        fois = re.search(r"--fois\s+(\d+)", l[8])
        res.append({"id": nom, "routine": routine, "heure": heure, "fois": int(fois.group(1)) if fois else 1,
                    "prochaine": l[2], "etat": l[3]})
    return sorted(res, key=lambda t: (ROUTINES.index(t["routine"]), t["heure"]))


def planifier(nom, heure, fois=1):
    """Ajoute (ou remplace, même routine et même heure) une tâche quotidienne de fois passages.
    Renvoie (ok, message)."""
    import lmagent
    import reglages
    if nom not in ROUTINES:
        return False, "Routine inconnue."
    if not HEURE.fullmatch(heure or ""):
        return False, "Heure au format HH:MM attendue (ex. 10:00)."
    try:
        fois = int(fois)
    except (TypeError, ValueError):
        return False, "Nombre de passages invalide."
    maxi = int(reglages.valeur("interface.passages_max"))
    if not 1 <= fois <= maxi:
        return False, f"Nombre de passages entre 1 et {maxi}."
    commande = subprocess.list2cmdline(lmagent.commande_soi() + ["--routine", nom, "--fois", str(fois)])
    r = _schtasks("/Create", "/TN", nom_tache(nom, heure), "/TR", commande, "/SC", "DAILY", "/ST", heure, "/F")
    if r.returncode != 0:
        return False, f"Planification impossible : {(r.stderr or r.stdout).strip()}"
    return True, f"« {nom} » planifiée tous les jours à {heure}" + (f" ({fois} passages)." if fois > 1 else ".")


def supprimer(id_tache):
    """Supprime une tâche de LMAgent (LMAgent_<routine>_<HHMM>, ou LMAgent_<routine> des versions précédentes)."""
    if not NOM_TACHE.match(id_tache or ""):
        return False, "Tâche inconnue."
    r = _schtasks("/Delete", "/TN", id_tache, "/F")
    if r.returncode != 0:
        return False, f"Suppression impossible : {(r.stderr or r.stdout).strip()}"
    return True, "Passage programmé supprimé."
