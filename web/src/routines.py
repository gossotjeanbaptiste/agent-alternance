"""Lancement des routines en arrière-plan et lecture de leur sortie."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from chemins import ALT, LOGS, ROOT

SCRIPTS = {"relances": ALT / "relances.py", "recherche": ALT / "recherche.py", "tout": ALT / "alternance.py"}
ROUTINE = {"proc": None, "nom": None, "fichier": None, "debut": None}


def en_cours():
    p = ROUTINE["proc"]
    return p is not None and p.poll() is None


def lancer(nom, essai=False):
    """Lance la routine dans un processus séparé ; sa sortie va dans logs/web_<date>_<nom>.txt."""
    LOGS.mkdir(exist_ok=True)
    fichier = LOGS / f"web_{datetime.now():%Y%m%d_%H%M%S}_{nom}{'_essai' if essai else ''}.txt"
    sortie = open(fichier, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-u", str(SCRIPTS[nom])] + (["--essai"] if essai else [])
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=sortie, stderr=subprocess.STDOUT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ROUTINE.update(proc=proc, nom=nom + (" (essai)" if essai else ""), fichier=fichier, debut=datetime.now())


def etat():
    p = ROUTINE["proc"]
    return {
        "en_cours": en_cours(),
        "nom": ROUTINE["nom"],
        "debut": ROUTINE["debut"].strftime("%H:%M:%S") if ROUTINE["debut"] else None,
        "code": None if p is None or p.poll() is None else p.returncode,
        "sortie": fin_de_fichier(ROUTINE["fichier"]) if ROUTINE["fichier"] else "",
    }


def historique(n=12):
    if not LOGS.exists():
        return []
    return [{"nom": f.name, "taille": f.stat().st_size} for f in sorted(LOGS.glob("web_*.txt"), reverse=True)[:n]]


def fichier_du_journal(nom, prefixe=""):
    """Chemin sûr d'un fichier de logs/ (refuse tout ce qui sort du dossier)."""
    f = (LOGS / nom).resolve()
    if f.parent != LOGS.resolve() or not f.name.startswith(prefixe) or not f.exists():
        return None
    return f


def fin_de_fichier(f, n=200):
    try:
        return "\n".join(Path(f).read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except Exception:
        return ""
