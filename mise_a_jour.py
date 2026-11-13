"""Mises à jour automatiques de la version installée, depuis les versions publiées sur GitHub.

Au lancement de l'interface (et toutes les 6 heures ensuite, si aucune routine ne tourne) :
1. demande à GitHub la dernière version publiée (tag vX.Y.Z) du dépôt indiqué dans les réglages ;
2. si elle est plus récente, télécharge le .msi et son empreinte .sha256, et vérifie l'empreinte ;
3. lance l'installation sans questions, avec la fenêtre de progression de Windows (msiexec /passive, comme
   MyCMS ; installation par utilisateur : pas de demande d'autorisation Windows)
   après la fermeture de LMAgent, puis relance LMAgent.

Rien ne se passe quand LMAgent tourne depuis le code (mise à jour par git), ni si le réglage
« mises_a_jour_auto » est décoché dans Paramètres.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import emplacements
from version import __version__

API = "https://api.github.com/repos/{depot}/releases/latest"
DEPOT_DEFAUT = "gossotjeanbaptiste/agent-alternance"
INTERVALLE_H = 6
ENTETES = {"User-Agent": f"LMAgent/{__version__}", "Accept": "application/vnd.github+json"}


def reglages():
    """(automatique ?, dépôt) d'après config.json."""
    try:
        c = json.loads(emplacements.config_agent().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        c = {}
    return bool(c.get("mises_a_jour_auto", True)), str(c.get("mises_a_jour_depot") or DEPOT_DEFAUT)


def numero(v):
    """« v1.2.10 » -> (1, 2, 10) ; texte illisible -> (0,)."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", str(v or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def plus_recente(distante, locale=__version__):
    return numero(distante) > numero(locale)


def derniere_version(depot):
    """{"version", "msi", "sha256"} de la dernière version publiée (URLs de téléchargement), ou None."""
    req = urllib.request.Request(API.format(depot=depot), headers=ENTETES)
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in d.get("assets") or []}
    msi = next((n for n in assets if n.lower().endswith(".msi")), None)
    sha = next((n for n in assets if msi and n.lower() == (msi + ".sha256").lower()), None)
    if not msi or not sha:
        return None
    return {"version": d.get("tag_name", ""), "msi": assets[msi], "sha256": assets[sha], "nom": msi}


def _telecharger(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": ENTETES["User-Agent"]})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while bloc := r.read(1 << 20):
            f.write(bloc)


def empreinte_attendue(texte):
    """Empreinte SHA-256 lue dans un fichier .sha256 (« <64 hex>  nom.msi »)."""
    m = re.search(r"\b[0-9a-fA-F]{64}\b", texte or "")
    return m.group(0).lower() if m else None


def empreinte(fichier):
    h = hashlib.sha256()
    with open(fichier, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def dossier_telechargement():
    """Dossier mises_a_jour/ (à côté de logs/), vidé à chaque téléchargement : rien ne s'accumule."""
    d = emplacements.dossier("mises_a_jour")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


def preparer(info, dossier=None):
    """Télécharge le .msi et vérifie son empreinte. Renvoie son chemin, ou lève une erreur."""
    dossier = Path(dossier or dossier_telechargement())
    msi = dossier / info["nom"]
    req = urllib.request.Request(info["sha256"], headers={"User-Agent": ENTETES["User-Agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        attendue = empreinte_attendue(r.read().decode("utf-8", errors="replace"))
    if not attendue:
        raise ValueError("empreinte SHA-256 illisible")
    _telecharger(info["msi"], msi)
    if empreinte(msi) != attendue:
        msi.unlink(missing_ok=True)
        raise ValueError("empreinte SHA-256 différente : fichier corrompu ou modifié, installation annulée")
    return msi


def _ps(texte):
    """Chaîne PowerShell entre apostrophes (une apostrophe s'écrit '')."""
    return "'" + str(texte).replace("'", "''") + "'"


def commande_installation(msi, pid=None, exe=None):
    """Commande PowerShell : attend la fermeture de LMAgent, installe (barre de progression, aucune question ;
    journal dans logs/), relance LMAgent."""
    logs = emplacements.dossier("logs")
    logs.mkdir(parents=True, exist_ok=True)
    journal = logs / f"installation_{Path(msi).stem}.txt"
    script = (f"Wait-Process -Id {pid or os.getpid()} -ErrorAction SilentlyContinue; "
              f"Start-Process msiexec.exe -Wait -ArgumentList "
              f"'/i',{_ps(chr(34) + str(msi) + chr(34))},'/passive','/norestart','/l*v',{_ps(chr(34) + str(journal) + chr(34))}; "
              f"Start-Process {_ps(exe or sys.executable)}")
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


def lancer_installation(msi):
    """Lance la commande d'installation dans un PowerShell sans fenêtre qui survit à la fermeture de LMAgent.
    Pas de DETACHED_PROCESS : sans console, PowerShell se ferme aussitôt sans rien faire (bug de la 1.0.0 à 1.0.3)."""
    sans_fenetre = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    hors_job = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    cmd = commande_installation(msi)
    try:
        subprocess.Popen(cmd, creationflags=sans_fenetre | hors_job, close_fds=True)
    except OSError:   # le processus n'a pas le droit de sortir de son groupe (job) : sans cette option
        subprocess.Popen(cmd, creationflags=sans_fenetre, close_fds=True)


def verifier(appliquer=True, journal=print):
    """Cherche une mise à jour et l'installe si besoin. Renvoie (installation_lancée, message)."""
    if not emplacements.INSTALLEE:
        return False, "Version lancée depuis le code : mise à jour par git (git pull)."
    auto, depot = reglages()
    try:
        info = derniere_version(depot)
    except Exception as e:
        return False, f"Vérification impossible ({e})."
    if not info:
        return False, "Aucune version publiée avec un installeur."
    if not plus_recente(info["version"]):
        return False, f"LMAgent est à jour (version {__version__})."
    if not appliquer:
        return False, f"Version {info['version']} disponible (installée version {__version__})."
    try:
        msi = preparer(info)
    except Exception as e:
        return False, f"Mise à jour {info['version']} abandonnée : {e}"
    journal(f"⬆️ Installation de la version {info['version']}, LMAgent va redémarrer…")
    lancer_installation(msi)
    return True, f"Installation de la version {info['version']} : LMAgent redémarre."


def surveiller(routine_en_cours, journal=print, fermer=lambda: os._exit(0)):
    """Vérifie toutes les INTERVALLE_H heures (fil en arrière-plan) ; installe si aucune routine ne tourne,
    puis ferme LMAgent avec fermer() (l'installeur le relance)."""
    import threading
    import time

    def boucle():
        while True:
            time.sleep(INTERVALLE_H * 3600)
            auto, _ = reglages()
            if auto and emplacements.INSTALLEE and not routine_en_cours():
                lancee, _ = verifier(journal=journal)
                if lancee:
                    fermer()
    threading.Thread(target=boucle, daemon=True).start()


def au_demarrage(journal=print):
    """Appelé avant d'ouvrir l'interface : renvoie True si LMAgent doit se fermer pour s'installer."""
    auto, _ = reglages()
    if not (emplacements.INSTALLEE and auto):
        return False
    lancee, message = verifier(journal=journal)
    journal(message)
    return lancee
