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


# Relance le script N fois d'affilée (chaque passage démarre quand le précédent est fini).
# Tourne dans le processus séparé : la boucle continue même si l'interface est arrêtée.
BOUCLE = """
import subprocess, sys
script, n, *args = sys.argv[1:]
n, code = int(n), 0
for i in range(n):
    if n > 1:
        print(f"\\n===== Passage {i + 1}/{n} =====\\n", flush=True)
    code = subprocess.call([sys.executable, "-u", script, *args]) or code
sys.exit(code)
"""


def lancer(nom, essai=False, fois=1):
    """Lance la routine (fois passages d'affilée) dans un processus séparé ;
    sa sortie va dans logs/web_<date>_<nom>.txt."""
    import reglages
    fois = max(1, min(int(fois), int(reglages.valeur("interface.passages_max"))))
    LOGS.mkdir(exist_ok=True)
    suffixe = (f"_x{fois}" if fois > 1 else "") + ("_essai" if essai else "")
    fichier = LOGS / f"web_{datetime.now():%Y%m%d_%H%M%S}_{nom}{suffixe}.txt"
    sortie = open(fichier, "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-u", "-c", BOUCLE, str(SCRIPTS[nom]), str(fois)] + (["--essai"] if essai else [])
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=sortie, stderr=subprocess.STDOUT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    libelle = nom + (f" ×{fois}" if fois > 1 else "") + (" (essai)" if essai else "")
    ROUTINE.update(proc=proc, nom=libelle, fichier=fichier, debut=datetime.now())


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
