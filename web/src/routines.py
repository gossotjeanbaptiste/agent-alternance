"""Lancement des routines en arrière-plan et lecture de leur sortie."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from chemins import ALT, LOGS, ROOT

SCRIPTS = {"relances": ALT / "relances.py", "recherche": ALT / "recherche.py", "tout": ALT / "alternance.py",
           "mails": ALT / "alternance.py", "reponses": ALT / "reponses_lba.py"}  # noms connus
ROUTINE = {"proc": None, "nom": None, "fichier": None, "debut": None}


def en_cours():
    p = ROUTINE["proc"]
    return p is not None and p.poll() is None


def commande(nom, essai=False, fois=1):
    """lmagent --routine <nom> [--fois N] [--essai] : l'exe dans la version installée, python lmagent.py sinon.
    La boucle des passages tourne dans ce processus séparé : elle continue même si l'interface est arrêtée."""
    import lmagent
    return lmagent.commande_soi() + ["--routine", nom, "--fois", str(fois)] + (["--essai"] if essai else [])


def lancer(nom, essai=False, fois=1):
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
    cmd = commande(nom, essai, fois)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=sortie, stderr=subprocess.STDOUT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    libelle = nom + (f" ×{fois}" if fois > 1 else "") + (" (essai)" if essai else "")
    ROUTINE.update(proc=proc, nom=libelle, fichier=fichier, debut=datetime.now(), annulee=False)


def annuler():
    """Arrête la routine lancée depuis l'interface, passages suivants compris (tout l'arbre de processus).
    Ce qui était fait reste fait (tableau et lettres enregistrés d'un seul coup : jamais à moitié écrits) ;
    le modèle, qu'elle n'a pas pu décharger, l'est ensuite en arrière-plan. Renvoie (ok, message)."""
    p = ROUTINE["proc"]
    if not en_cours():
        return False, "Aucune routine en cours."
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        p.wait(timeout=15)
    except subprocess.TimeoutExpired:
        return False, "La routine ne s'arrête pas : réessaie dans un instant."
    ROUTINE["annulee"] = True
    try:
        with open(ROUTINE["fichier"], "a", encoding="utf-8") as f:
            f.write(f"\n⛔ Routine annulée depuis l'interface à {datetime.now():%H:%M:%S}.\n")
    except OSError:
        pass
    import threading
    threading.Thread(target=decharger_modele, daemon=True).start()
    return True, "Routine annulée : ce qui était fait est gardé, le modèle est déchargé."


def decharger_modele():
    """Décharge le modèle des routines là où il est chargé (tour, ce PC) : une routine arrêtée de force n'a pas pu
    le faire. LM Studio reste ouvert ; seul le modèle réglé dans config.json est concerné."""
    import json
    import urllib.request
    import agent
    modele = agent.CONFIG.get("modele")
    bases = []
    for s in agent.CONFIG.get("serveurs") or [{"url": "local"}]:
        url = str(s.get("url") or "")
        bases += ["http://localhost:1234", "http://localhost:1235"] if url == "local" else [url.removesuffix("/v1")]
    dechargees = 0
    for base in dict.fromkeys(bases):
        try:
            with urllib.request.urlopen(base + "/api/v1/models", timeout=5) as r:
                infos = json.loads(r.read())
        except Exception:
            continue                      # serveur éteint ou injoignable : rien à décharger
        for m in infos.get("models", []):
            if m.get("key") != modele:
                continue
            for inst in m.get("loaded_instances") or []:
                req = urllib.request.Request(base + "/api/v1/models/unload", method="POST",
                                             data=json.dumps({"instance_id": inst["id"]}).encode(),
                                             headers={"Content-Type": "application/json"})
                try:
                    urllib.request.urlopen(req, timeout=60).close()
                    dechargees += 1
                except Exception:
                    pass
    return dechargees


def etat():
    p = ROUTINE["proc"]
    return {
        "en_cours": en_cours(),
        "annulee": bool(ROUTINE.get("annulee")) and not en_cours(),
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
