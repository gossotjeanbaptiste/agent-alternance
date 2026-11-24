"""Mise à jour de LMAgent lancé depuis le code (bouton « Vérifier maintenant » de Paramètres) : nouveautés de la
branche récupérées par git (avance rapide seulement, jamais si des fichiers suivis ont été modifiés à la main),
puis l'interface se relance d'elle-même, sans rouvrir le navigateur (la page ouverte se recharge)."""
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]       # dossier du dépôt (src/ est juste dessous)
SANS_NAVIGATEUR = "LMAGENT_SANS_NAVIGATEUR"        # relance : la page déjà ouverte se recharge toute seule


def _git(*args, timeout=120):
    """(code de sortie, sortie) d'une commande git lancée dans le dépôt."""
    try:
        r = subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return r.returncode, (r.stdout + r.stderr).strip()


def mettre_a_jour(appliquer=True):
    """Récupère les nouveautés de la branche (git pull --ff-only). Renvoie (relancer, message) :
    relancer est vrai quand du nouveau code a été récupéré (l'interface doit redémarrer pour le prendre)."""
    code, branche = _git("rev-parse", "--abbrev-ref", "HEAD")
    if code:
        return False, f"Mise à jour par git impossible : {branche or 'git introuvable'}."
    code, sortie = _git("fetch", "--quiet")
    if code:
        return False, f"Vérification impossible (git fetch : {sortie})."
    code, retard = _git("rev-list", "--count", "HEAD..@{u}")
    if code:
        return False, f"La branche {branche} ne suit aucune branche distante : mise à jour par git impossible."
    n = int(retard or 0)
    if not n:
        return False, f"LMAgent est à jour (branche {branche})."
    if not appliquer:
        return False, f"{n} nouveauté(s) disponible(s) sur la branche {branche}."
    code, modifies = _git("status", "--porcelain", "--untracked-files=no")
    if modifies:
        return False, (f"{n} nouveauté(s) sur la branche {branche}, mais des fichiers du code ont été modifiés "
                       "sur ce PC : mise à jour annulée (enregistre ou annule ces modifications avec git).")
    code, sortie = _git("pull", "--ff-only", "--quiet")
    if code:
        return False, f"Mise à jour annulée (git pull : {sortie})."
    return True, f"{n} nouveauté(s) récupérée(s) (branche {branche}) : l'interface redémarre."


def commande_relance(pid=None):
    """PowerShell : attend la fermeture de l'interface, puis la relance (même commande, sans fenêtre ni
    nouvel onglet de navigateur)."""
    from mise_a_jour import _ps
    script_lance = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else RACINE / "lmagent.py"
    arguments = ",".join(_ps(chr(34) + a + chr(34)) for a in [str(script_lance), *sys.argv[1:]])   # chemins avec espaces
    script = (f"Wait-Process -Id {pid or os.getpid()} -ErrorAction SilentlyContinue; "
              f"$env:{SANS_NAVIGATEUR} = '1'; "
              f"Start-Process {_ps(sys.executable)} -ArgumentList {arguments} "
              f"-WorkingDirectory {_ps(RACINE)} -WindowStyle Hidden")
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


def lancer_relance():
    """Prépare la relance, qui part dès que l'interface s'est fermée."""
    from mise_a_jour import lancer_detache
    lancer_detache(commande_relance())
