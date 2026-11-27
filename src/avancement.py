"""Avancement de la routine en cours, lu en direct par la page Routines (aussi pour une routine programmée par le
Planificateur de tâches, que l'interface n'a pas lancée).

Fichier taches/avancement.json : {pid (processus de la routine ou de sa boucle de passages), cree (heure de création de
ce processus : un numéro repris plus tard par un autre programme ne passe pas pour la routine), routine, passage,
total, etape, detail, k, n, debut, maj, sortie (journal de la routine), fini, code}.
- lmagent.routine : commencer() au lancement, passage() avant chaque passage, finir() à la fin ;
- pendant un passage : etape("Rédaction des candidatures", "Forgeval Dev", 2, 5).
Écrit d'un seul coup (fichier à côté puis remplacé) : la page ne lit jamais un fichier à moitié écrit.
Toute erreur est ignorée : l'avancement ne doit jamais gêner la routine.
"""
import json
import os
import subprocess
import time
from datetime import datetime

import emplacements

PROCESSUS = ("lmagent.exe", "python.exe", "pythonw.exe", "py.exe")   # ce qui peut faire tourner une routine


def fichier():
    return emplacements.dossier("taches") / "avancement.json"


def lire():
    try:
        d = json.loads(fichier().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    f = fichier()
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    for _ in range(5):          # fichier lu au même instant par la page : Windows refuse de le remplacer, on réessaie
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, f)
            return
        except OSError:
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)


def creation(pid):
    """Heure de création du processus pid (compteur Windows), ou None (introuvable, autre système)."""
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            t = [wintypes.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
                return None
            return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
        finally:
            k.CloseHandle(h)
    except (AttributeError, OSError, ValueError):
        return None


def _maj(**champs):
    d = lire()
    d.update(champs, maj=datetime.now().isoformat(timespec="seconds"))
    _ecrire(d)


def commencer(routine, total=1, essai=False):
    """Début d'une routine (ou de sa boucle de passages) : ce processus en est le responsable."""
    if os.environ.get("LMAGENT_BOUCLE"):        # passage d'une boucle : la boucle a déjà tout noté
        return
    _ecrire({"pid": os.getpid(), "cree": creation(os.getpid()), "routine": routine, "essai": essai, "passage": 1, "total": total,
             "etape": "Démarrage", "detail": "", "k": None, "n": None, "fini": False, "code": None,
             "debut": datetime.now().isoformat(timespec="seconds"), "maj": datetime.now().isoformat(timespec="seconds"),
             "sortie": os.environ.get("LMAGENT_SORTIE") or ""})


def passage(i, total):
    _maj(passage=i, total=total, etape="Démarrage du passage", detail="", k=None, n=None)


def etape(texte, detail="", k=None, n=None):
    """Étape en cours d'un passage ; k / n : entreprise k sur n (None : pas de compteur)."""
    _maj(etape=texte, detail=str(detail or ""), k=k, n=n)


def finir(code=0):
    if os.environ.get("LMAGENT_BOUCLE"):        # la boucle note la fin après le dernier passage
        return
    _maj(fini=True, code=code, etape="Terminée" if not code else "Terminée avec une erreur", detail="", k=None, n=None)


def annulee():
    """Routine arrêtée de force depuis l'interface (ses processus n'ont pas pu le noter eux-mêmes)."""
    _maj(fini=True, code=-1, etape="Annulée", detail="", k=None, n=None)


def processus_actif(pid):
    """Vrai si le processus pid tourne encore et fait tourner LMAgent (numéro repris par un autre programme : non)."""
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH", "/FO", "CSV"], capture_output=True,
                           text=True, errors="replace", timeout=10)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    premiere = r.stdout.strip().splitlines()[0].lower() if r.stdout.strip() else ""
    return premiere.startswith('"') and premiere.split('","')[0].strip('"') in PROCESSUS


def en_cours():
    """Avancement de la routine qui tourne en ce moment (lancée par l'interface ou programmée), sinon None.
    Routine arrêtée net (fichier resté « pas fini ») dont le numéro a été repris par un autre programme, même LMAgent
    ou Python : écartée grâce à l'heure de création du processus."""
    d = lire()
    if not d or d.get("fini") or not d.get("pid") or int(d["pid"]) == os.getpid():
        return None
    if d.get("cree") is not None and creation(d["pid"]) != d["cree"]:
        return None
    if not processus_actif(d["pid"]):
        return None
    return d
