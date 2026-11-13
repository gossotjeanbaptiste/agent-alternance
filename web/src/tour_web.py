"""État et pilotage de la tour depuis l'interface (absent sur la branche 100 % locale)."""
import subprocess
import threading
from datetime import datetime

import chemins  # noqa: F401

try:
    import tour
except Exception:
    tour = None

ACTIONS = ("reveiller", "serveur", "veille", "fermer_lmstudio")
ETAT = {"action": None, "messages": []}


def disponible():
    return tour is not None


def etat():
    ts = subprocess.run([r"C:\Program Files\Tailscale\tailscale.exe", "status"], capture_output=True,
                        text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"lmstudio": tour.lmstudio_ok(), "ssh": tour.ssh_ok(), "ssh_lan": tour.ssh_lan_ok(),
            "tailscale": ts.returncode == 0 and "stopped" not in ts.stdout.lower()}


def lancer_action(nom):
    """Lance l'action dans un fil séparé (le réveil peut prendre plusieurs minutes)."""
    if ETAT["action"]:
        return False, f"Action « {ETAT['action']} » déjà en cours."
    ETAT["action"] = nom
    threading.Thread(target=_executer, args=(nom,), daemon=True).start()
    return True, "Action lancée."


def _executer(nom):
    def log(m):
        ETAT["messages"].append(f"[{datetime.now():%H:%M:%S}] {m.strip()}")
    ETAT["messages"] = []
    try:
        if nom == "reveiller":
            tour.reveiller(log=log)
        elif nom == "serveur":
            tour.demarrer_serveur(log=log)
        elif nom == "veille":
            tour.veille(log=log)
        elif nom == "fermer_lmstudio":
            tour.LMSTUDIO_OUVERT_PAR_SCRIPT = True
            tour.fermer_lmstudio_si_ouvert(log=log)
        log("Terminé.")
    except Exception as e:
        log(f"Erreur : {e}")
    finally:
        ETAT["action"] = None
