"""Pas de fenêtre de terminal qui clignote pour les commandes lancées en arrière-plan.

Une routine lancée par l'interface (ou par le Planificateur) tourne sans console : chaque commande qu'elle lance
(tasklist, powershell, lms, schtasks, passage suivant d'une boucle…) ouvrirait alors sa propre fenêtre de terminal,
le temps d'un éclair. `activer()` ajoute CREATE_NO_WINDOW à toutes ces commandes, tant que le processus n'a pas
de console à leur prêter. Sans effet sur les applications à fenêtre (Outlook, LM Studio) ni hors de Windows.
"""
import subprocess
import sys

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
_ORIGINAL = _VRAI = subprocess.Popen.__init__


def a_une_console():
    """Vrai si le processus a une fenêtre de console (que ses commandes partagent sans en ouvrir d'autre)."""
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except (AttributeError, OSError):
        return True


def drapeaux(creationflags, console):
    """Drapeaux de création à utiliser : CREATE_NO_WINDOW ajouté sans console, sauf choix explicite de fenêtre."""
    if console or creationflags & (CREATE_NEW_CONSOLE | DETACHED_PROCESS):
        return creationflags
    return creationflags | CREATE_NO_WINDOW


def _init(self, *args, creationflags=0, **kwargs):
    _ORIGINAL(self, *args, creationflags=drapeaux(creationflags, a_une_console()), **kwargs)


def activer():
    """À appeler une fois au démarrage (lmagent.main)."""
    if sys.platform == "win32" and subprocess.Popen.__init__ is not _init:
        subprocess.Popen.__init__ = _init


def desactiver():
    subprocess.Popen.__init__ = _VRAI
