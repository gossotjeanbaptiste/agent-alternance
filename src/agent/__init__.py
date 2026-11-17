"""
Agent IA local — LM Studio + Qwen3.5 9B
Aucune dépendance externe (bibliothèque standard Python uniquement).

Modes :
    python lmagent.py --agent                   -> chat interactif (demande avant chaque action)
    python lmagent.py --agent --tache trier     -> exécute taches/trier.txt sans intervention
    python lmagent.py --agent --task "consigne" -> exécute une consigne sans intervention

Réglages : config.json   |   Journal : logs/   |   Fichiers "supprimés" : corbeille/

Ce paquet tient la configuration et l'état partagé (serveur choisi, modèles à décharger…). Ses modules lisent
cet état et s'appellent entre eux par `agent.X` : une valeur ou une fonction se remplace (tests) à un seul endroit.
    fichiers.py      outils de fichiers proposés au modèle (limités aux dossiers autorisés)
    outils.py        PowerShell, page web, liste des outils et consigne système
    lmstudio.py      appels de base à LM Studio (API REST, lms.exe)
    moteur.py        choix du moteur selon la carte graphique
    serveur.py       choix du serveur (tour puis ce PC), chargement du modèle, requêtes
    liberation.py    à la fin : modèle déchargé, LM Studio refermé, tour rendormie
    conversation.py  chat interactif, tâches automatiques, ligne de commande
"""
import atexit
import json
import os
from datetime import datetime
from pathlib import Path

import emplacements  # où vivent config, journaux… : dossier du projet ou %APPDATA%\LMAgent

WORKSPACE = emplacements.dossier("workspace")
CORBEILLE = emplacements.dossier("corbeille")
LOGS = emplacements.dossier("logs")
TACHES = emplacements.dossier("taches")
for d in (WORKSPACE, CORBEILLE, LOGS, TACHES):
    d.mkdir(parents=True, exist_ok=True)

CONFIG = {
    "modele": "qwen/qwen3.5-9b",
    "contexte": 16384,
    "dossiers_autorises": [],
    "powershell_en_auto": False,
    "etapes_max": 20,
    "afficher_reflexion": False,
}
if emplacements.config_agent().exists():
    CONFIG.update(json.loads(emplacements.config_agent().read_text(encoding="utf-8")))


def utiliser_tour(config=None):
    """Vrai si un deuxième PC (la tour) fait tourner l'IA. Réglage « utiliser_tour » ; s'il est absent
    (anciennes configs), déduit de la liste des serveurs (un serveur autre que « ce PC »)."""
    c = CONFIG if config is None else config
    if "utiliser_tour" in c:
        return bool(c["utiliser_tour"])
    return any(s.get("url") != "local" for s in c.get("serveurs") or [])


LMS = Path(os.path.expanduser(CONFIG.get("lms_local") or "~/.lmstudio/bin/lms.exe"))
ALLOWED = [WORKSPACE] + [Path(os.path.expanduser(p)).resolve() for p in CONFIG["dossiers_autorises"]]
AUTO = False          # passe à True en mode --task / --tache
BASE_URL = None       # choisi par ensure_server()
SERVEUR = "?"         # nom du PC qui fait tourner le modèle (pour le journal)
A_DECHARGER = []      # modèles chargés par le script, déchargés à la fin pour libérer la VRAM
TOUR_REVEILLEE = False  # True si c'est le script qui a sorti la tour de veille -> on la rendort à la fin
LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT = False  # True si LM Studio était fermé sur ce PC -> on le referme à la fin


# --- Journal -----------------------------------------------------------------
def log(msg: str):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    with open(LOGS / f"{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def say(msg: str):
    print(msg)
    log(msg)


# --- Les parties de l'agent (importées après l'état, qu'elles lisent par agent.X) ----------------
from .fichiers import (_confirm, _safe_path, _to_trash, create_folder, delete_file, disk_space,  # noqa: E402
                       list_dir, move_file, read_file, write_file)
from .outils import TOOL_SCHEMAS, TOOLS, fetch_url, run_powershell, system_prompt  # noqa: E402
from .lmstudio import _api, _lms, _lmstudio_local_ouvert, _reachable  # noqa: E402
from .moteur import _cuda, _moteurs_installes, _version, cartes_graphiques, choisir_moteur, type_gpu  # noqa: E402
from .serveur import _charger_distant, _serveur_local, ensure_server, post_chat  # noqa: E402
from .liberation import (_garder_pour_le_passage_suivant, _reprendre_boucle, fermer_lmstudio,  # noqa: E402
                         liberer_modele, remettre_tour_en_veille)
from .conversation import chat, main, run_auto, run_chat, run_turn  # noqa: E402

atexit.register(lambda: liberer_modele())   # en passant par le paquet : la version en place à la fin
