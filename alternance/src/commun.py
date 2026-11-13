"""Réglages et outils partagés par tous les modules de la routine d'alternance."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # dossier alternance/ (config, profil, tableau)
sys.path.insert(0, str(HERE.parent))            # racine du projet (agent.py)
import agent  # noqa: E402,F401  (connexion LM Studio, journal)

CFG = json.loads((HERE / "config_alternance.json").read_text(encoding="utf-8"))
PROFIL = (HERE / "profil.md").read_text(encoding="utf-8")
ESSAI = False   # True avec --essai : rien n'est écrit (ni brouillon, ni Excel)
GARDE = None    # minuteur qui arrête tout si la lecture d'Outlook se bloque


def P(p):
    """Chemin avec ~ développé."""
    return Path(os.path.expanduser(p))


def say(msg):
    agent.say(msg)
