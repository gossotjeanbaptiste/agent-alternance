"""Lancement des routines en arrière-plan et lecture de leur sortie."""
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from chemins import ALT, LOGS, ROOT
from dechargement import decharger_modele  # noqa: F401  (routines.decharger_modele : remplacé par les tests)

SCRIPTS = {"relances": ALT / "relances.py", "recherche": ALT / "recherche.py", "tout": ALT / "alternance.py",
           "mails": ALT / "alternance.py", "reponses": ALT / "reponses_lba.py"}  # noms connus
ROUTINE = {"proc": None, "nom": None, "fichier": None, "debut": None}
_EXTERNE = {"quand": 0, "etat": None}     # routine lancée hors de cette interface, vérifiée au plus toutes les 3 s


def lancee_ici():
    """Vrai si la routine lancée par cette interface tourne encore."""
    p = ROUTINE["proc"]
    return p is not None and p.poll() is None


def externe():
    """Avancement (src/avancement.py) d'une routine qui tourne sans avoir été lancée par cette interface : routine
    programmée par le Planificateur de tâches, ou lancée avant que l'interface soit relancée. None sinon."""
    if lancee_ici():
        return None
    if time.time() - _EXTERNE["quand"] > 3:
        import avancement
        _EXTERNE.update(quand=time.time(), etat=avancement.en_cours())
    return _EXTERNE["etat"]


def en_cours():
    """Une routine tourne (lancée ici ou programmée) : le tableau ne doit pas être modifié depuis l'interface."""
    return lancee_ici() or externe() is not None


def commande(nom, essai=False, fois=1, depuis=None):
    """lmagent --routine <nom> [--fois N] [--essai] : l'exe dans la version installée, python lmagent.py sinon.
    La boucle des passages tourne dans ce processus séparé : elle continue même si l'interface est arrêtée."""
    import lmagent
    return (lmagent.commande_soi() + ["--routine", nom, "--fois", str(fois)] + (["--essai"] if essai else [])
            + (["--depuis", depuis.isoformat()] if depuis else []))


def lancer(nom, essai=False, fois=1, depuis=None):
    """Lance la routine (fois passages d'affilée) dans un processus séparé ;
    sa sortie va dans logs/web_<date>_<nom>.txt."""
    import reglages
    fois = max(1, min(int(fois), int(reglages.valeur("interface.passages_max"))))
    LOGS.mkdir(exist_ok=True)
    suffixe = (f"_x{fois}" if fois > 1 else "") + ("_essai" if essai else "")
    fichier = LOGS / f"web_{datetime.now():%Y%m%d_%H%M%S}_{nom}{suffixe}.txt"
    sortie = open(fichier, "a", encoding="utf-8")   # ajout en fin de fichier, quel que soit le processus qui écrit
    # LMAGENT_SORTIE : l'exe installé (sans console) écrit lui-même dans ce fichier
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", LMAGENT_SORTIE=str(fichier))
    cmd = commande(nom, essai, fois, depuis)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=sortie, stderr=subprocess.STDOUT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    libelle = nom + (f" ×{fois}" if fois > 1 else "") + (f", mails depuis le {depuis:%d/%m}" if depuis else "")
    libelle += " (essai)" if essai else ""
    ROUTINE.update(proc=proc, nom=libelle, fichier=fichier, debut=datetime.now(), annulee=False)


def annuler():
    """Arrête la routine lancée depuis l'interface, passages suivants compris (tout l'arbre de processus).
    Ce qui était fait reste fait (tableau et lettres enregistrés d'un seul coup : jamais à moitié écrits) ;
    le modèle, qu'elle n'a pas pu décharger, l'est ensuite en arrière-plan. Renvoie (ok, message)."""
    p = ROUTINE["proc"]
    if not lancee_ici():
        return _annuler_externe()
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        p.wait(timeout=15)
    except subprocess.TimeoutExpired:
        return False, "La routine ne s'arrête pas : réessaie dans un instant."
    ROUTINE["annulee"] = True
    import avancement
    avancement.annulee()
    return _apres_annulation(ROUTINE["fichier"])


def _annuler_externe():
    """Arrête une routine programmée : seulement si son numéro de processus fait bien tourner LMAgent."""
    import avancement
    d = externe()
    if not d:
        return False, "Aucune routine en cours."
    if not avancement.en_cours():          # revérifié juste avant l'arrêt (numéro et heure de création du processus)
        _EXTERNE["quand"] = 0
        return False, "Cette routine n'est plus en cours."
    subprocess.run(["taskkill", "/PID", str(int(d["pid"])), "/T", "/F"], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _EXTERNE["quand"] = 0
    avancement.annulee()
    return _apres_annulation(fichier_du_journal(Path(d.get("sortie") or "").name, prefixe="web_"))


def _apres_annulation(fichier):
    """Note l'annulation dans le journal de la routine et décharge le modèle en arrière-plan."""
    try:
        with open(fichier, "a", encoding="utf-8") as f:
            f.write(f"\n⛔ Routine annulée depuis l'interface à {datetime.now():%H:%M:%S}.\n")
    except (OSError, TypeError):   # journal inconnu (routine lancée depuis le code)
        pass
    import threading
    threading.Thread(target=decharger_modele, daemon=True).start()
    return True, "Routine annulée : ce qui était fait est gardé, le modèle est déchargé."


NOMS = {"relances": "Relances", "recherche": "Recherche", "tout": "Les deux", "mails": "Mails reçus",
        "reponses": "Réponses La Bonne Alternance"}


def etat():
    """Routine lancée ici (en cours ou dernière), sinon routine programmée en cours ; avec son avancement."""
    import avancement
    p = ROUTINE["proc"]
    d = externe()
    if d:
        sortie = fichier_du_journal(Path(d.get("sortie") or "").name, prefixe="web_") if d.get("sortie") else None
        return {"en_cours": True, "externe": True, "annulee": False, "code": None,
                "nom": NOMS.get(d.get("routine"), d.get("routine")) + " (programmée)",
                "debut": str(d.get("debut") or "")[11:19], "avancement": d,
                "sortie": fin_de_fichier(sortie, 400) if sortie else "Journal non disponible (routine lancée depuis le code, "
                                                                       "sa sortie va dans sa propre fenêtre)."}
    ici = lancee_ici()
    return {
        "en_cours": ici,
        "externe": False,
        "annulee": bool(ROUTINE.get("annulee")) and not ici,
        "nom": ROUTINE["nom"],
        "debut": ROUTINE["debut"].strftime("%H:%M:%S") if ROUTINE["debut"] else None,
        "code": None if p is None or p.poll() is None else p.returncode,
        "avancement": avancement.lire() if ici else None,
        "sortie": fin_de_fichier(ROUTINE["fichier"], 400) if ROUTINE["fichier"] else "",
    }


def libelle_lancement(nom):
    """« web_20261126_134722_tout_x3_essai.txt » -> « 26/11 à 13:47 — Les deux ×3 (essai) »."""
    import re
    m = re.match(r"web_(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)\d\d_([a-z]+)(.*)\.txt$", nom)
    if not m:
        return nom
    a, mo, j, h, mi, routine, reste = m.groups()
    fois = re.search(r"_x(\d+)", reste)
    return (f"{j}/{mo} à {h}:{mi} — {NOMS.get(routine, routine)}" + (f" ×{fois.group(1)}" if fois else "")
            + (" (programmée)" if "_planifiee" in reste else "") + (" (essai)" if "_essai" in reste else ""))


def historique(n=15):
    if not LOGS.exists():
        return []
    return [{"nom": f.name, "libelle": libelle_lancement(f.name), "taille": f.stat().st_size}
            for f in sorted(LOGS.glob("web_*.txt"), reverse=True)[:n]]


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
