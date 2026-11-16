"""Où vivent les fichiers personnels (config, données, journaux, export LinkedIn, pièces jointes…).

- Lancé depuis le code source : dans le dossier perso/ du projet (config.json, logs/, linkedin/, pieces_jointes/,
  workspace/, corbeille/, taches/), sauf les données de la routine, dans alternance/donnees/ à côté de leurs modèles.
  Les anciens fichiers posés à la racine du projet y sont rangés tout seuls (ranger_racine).
- Version installée (.exe) : dans %APPDATA%\\LMAgent\\ (jamais touché par l'installeur ni par les mises à jour),
  avec les mêmes sous-dossiers, sauf les données de la routine directement dans donnees/.
- Variable d'environnement LMAGENT_DOSSIER : force un autre dossier (tests, installation portable).

Les fichiers fournis avec l'appli (modèles d'exemple, pages web, logo) restent à côté du code : voir RESSOURCES.
"""
import os
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent               # racine du projet (ce fichier est dans src/)
INSTALLEE = bool(getattr(sys, "frozen", False))                 # True dans le .exe (PyInstaller)
RESSOURCES = Path(getattr(sys, "_MEIPASS", SOURCE))             # fichiers fournis avec l'appli


def _base():
    force = os.environ.get("LMAGENT_DOSSIER")
    if force:
        return Path(force), False
    if INSTALLEE:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "LMAgent", False
    return SOURCE / "perso", True


BASE, DEPUIS_LE_CODE = _base()
# anciens emplacements, à la racine du projet (avant le dossier perso/)
ANCIENS = ("config.json", "logs", "linkedin", "pieces_jointes", "workspace", "corbeille", "taches")


def config_agent():
    """config.json : réglages de l'agent, du modèle et de la tour."""
    return BASE / "config.json"


def donnees():
    """Données de la routine (config, profil, contre-prompt, tableau, réponses, refus, compte de l'interface)."""
    return SOURCE / "alternance" / "donnees" if DEPUIS_LE_CODE else BASE / "donnees"


def dossier(nom):
    """Sous-dossier personnel : logs, linkedin, pieces_jointes, workspace, corbeille, taches."""
    return BASE / nom


def modeles():
    """Modèles d'exemple fournis avec l'appli (*.example.*)."""
    return RESSOURCES / "alternance" / "donnees"


def ranger_racine(source=None, base=None, journal=print):
    """Lancé depuis le code : range dans perso/ les fichiers personnels encore à la racine du projet.
    Rien n'est écrasé : un élément déjà présent dans perso/ reste à la racine (et c'est signalé).
    Renvoie la liste des éléments déplacés."""
    source, base = Path(source or SOURCE), Path(base or BASE)
    deplaces = []
    for nom in ANCIENS:
        ancien, nouveau = source / nom, base / nom
        if not ancien.exists() or ancien.resolve() == nouveau.resolve():
            continue
        if nouveau.exists():
            journal(f"⚠️ {nom} existe à la fois à la racine du projet et dans perso/ : celui de la racine n'est pas déplacé")
            continue
        base.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ancien), str(nouveau))
        deplaces.append(nom)
    if deplaces:
        journal(f"📁 Fichiers personnels rangés dans {base} : {', '.join(deplaces)}")
    return deplaces


def ranger_au_demarrage(journal=print):
    """Appelé au démarrage réel de l'appli (commun.py), jamais au simple chargement de ce module :
    lancé depuis le code, range la racine du projet dans perso/."""
    if not DEPUIS_LE_CODE:
        return []
    try:
        return ranger_racine(journal=journal)
    except OSError as e:      # fichier ouvert ailleurs… : on réessaiera au prochain lancement
        journal(f"⚠️ Rangement dans perso/ impossible pour l'instant ({e})")
        return []
