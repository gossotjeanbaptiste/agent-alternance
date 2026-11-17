"""
Pilotage de la tour à distance (depuis le ThinkPad).

    python src\\tour etat          -> la tour est-elle allumée ? LM Studio ? SSH ?
    python src\\tour reveiller     -> Wake-on-LAN si elle dort + démarre le serveur LM Studio si besoin
    python src\\tour serveur       -> démarre le serveur LM Studio de la tour (l'ouvre si besoin)
    python src\\tour fermer-lmstudio -> ferme LM Studio sur la tour
    python src\\tour tailscale     -> relance Tailscale sur ce PC, et sur la tour si besoin
    python src\\tour veille        -> met la tour en veille
    python src\\tour eteindre      -> éteint la tour (60 s de délai, annulable)
    python src\\tour redemarrer    -> redémarre la tour
    python src\\tour annuler       -> annule un arrêt / redémarrage en cours
    ajoute --oui pour ne pas avoir de confirmation, --maintenant pour éteindre sans délai

Réglages : rubrique "tour" de config.json (valeurs par défaut dans config.py).
- Le réveil (Wake-on-LAN) est envoyé sur le réseau local ET à la box par Internet
  (rubrique "wol_internet") : la box le relaie vers la tour, donc ça marche aussi hors de chez toi.
- Veille / arrêt / démarrage de LM Studio passent par SSH via Tailscale (de partout), ou par le
  réseau local ("ssh_lan") si Tailscale est coupé sur la tour.

Ce paquet tient l'état partagé ; ses modules le lisent et s'appellent entre eux par `tour.X` (une valeur ou une
fonction se remplace, dans les tests, à un seul endroit) :
    config.py        réglages de la tour (config.json, avec des valeurs par défaut)
    ssh.py           connexion SSH (Tailscale, sinon réseau local), scripts PowerShell à distance
    lmstudio.py      LM Studio sur la tour : ouvert ?, ouverture dans la session, serveur, fermeture
    diagnostic.py    pourquoi LM Studio ne démarre pas (lecture seule) et erreurs PowerShell lisibles
    reseau.py        Tailscale, Wake-on-LAN, réveil complet
    gpu.py           carte graphique déjà occupée (jeu…) ?
    alimentation.py  veille, arrêt, redémarrage
    cli.py           ligne de commande
"""
import html  # noqa: F401  (utilisé par diagnostic.py)
import time  # noqa: F401  (tour.time.sleep remplacé dans les tests)

from .config import T, _cfg  # noqa: F401


def _print(msg):
    print(msg, flush=True)


LMSTUDIO_OUVERT_PAR_SCRIPT = False  # True si LM Studio était fermé sur la tour et que le script l'a ouvert
TACHE_LMSTUDIO = "lm_agent_lmstudio"
TAILSCALE_LOCAL = T.get("tailscale_local") or r"C:\Program Files\Tailscale\tailscale.exe"

from .ssh import _cible_ssh, _port_ouvert, _ssh_action, _ssh_brut, ps_distant, ssh, ssh_lan_ok, ssh_ok  # noqa: E402
from .diagnostic import diagnostic_lmstudio, erreur_powershell, lire_diagnostic  # noqa: E402
from .lmstudio import (demarrer_serveur, fermer_lmstudio_si_ouvert, lmstudio_ok, lmstudio_ouvert_tour,  # noqa: E402
                       modele_charge, ouvrir_lmstudio_tour)
from .reseau import relancer_tailscale_tour, reveiller, tailscale_local, wake_on_lan  # noqa: E402
from .gpu import analyser_nvidia_smi, gpu_occupe, lire_gpu  # noqa: E402
from .alimentation import annuler, eteindre, redemarrer, veille  # noqa: E402
from .cli import main  # noqa: E402
