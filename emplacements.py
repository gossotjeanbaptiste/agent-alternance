"""Où vivent les fichiers personnels (config, données, journaux, export LinkedIn, pièces jointes…).

- Lancé depuis le code source : comme toujours, dans le dossier du projet (config.json à la racine,
  alternance/donnees/, logs/, linkedin/, pieces_jointes/, workspace/, corbeille/, taches/).
- Version installée (.exe) : dans %APPDATA%\\LMAgent\\ (jamais touché par l'installeur ni par les mises à jour),
  avec les mêmes sous-dossiers, sauf les données de la routine directement dans donnees/.
- Variable d'environnement LMAGENT_DOSSIER : force un autre dossier (tests, installation portable).

Les fichiers fournis avec l'appli (modèles d'exemple, pages web, logo) restent à côté du code : voir RESSOURCES.
"""
import os
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent                      # dossier du code (ou du .exe extrait)
INSTALLEE = bool(getattr(sys, "frozen", False))                 # True dans le .exe (PyInstaller)
RESSOURCES = Path(getattr(sys, "_MEIPASS", SOURCE))             # fichiers fournis avec l'appli


def _base():
    force = os.environ.get("LMAGENT_DOSSIER")
    if force:
        return Path(force), False
    if INSTALLEE:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "LMAgent", False
    return SOURCE, True


BASE, DEPUIS_LE_CODE = _base()


def config_agent():
    """config.json : réglages de l'agent, du modèle et de la tour."""
    return BASE / "config.json"


def donnees():
    """Données de la routine (config, profil, contre-prompt, tableau, réponses, refus, compte de l'interface)."""
    return BASE / "alternance" / "donnees" if DEPUIS_LE_CODE else BASE / "donnees"


def dossier(nom):
    """Sous-dossier personnel : logs, linkedin, pieces_jointes, workspace, corbeille, taches."""
    return BASE / nom


def modeles():
    """Modèles d'exemple fournis avec l'appli (*.example.*)."""
    return RESSOURCES / "alternance" / "donnees"
