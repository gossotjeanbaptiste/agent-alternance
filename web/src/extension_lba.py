"""Échange avec l'extension Chrome de LMAgent (dossier web/extension) pour préremplir le formulaire La Bonne Alternance
dans le Chrome habituel de l'utilisateur.

Sécurité :
- les données d'une candidature sont déposées sous un jeton tiré au hasard (256 bits), valable 2 minutes et
  utilisable UNE seule fois ; il n'est transmis que dans l'adresse ouverte dans Chrome (#lmagent=…), que
  l'extension efface aussitôt ;
- le point d'entrée /api/extension/<jeton> n'accepte que l'origine de l'extension LMAgent (identifiant fixe,
  tiré de la clé de son manifest) : une page web ne peut pas lire ces données ;
- l'extension n'a aucune permission sur les cookies, les onglets ou les autres sites (voir son manifest).
"""
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ID_EXTENSION = "cckhnfpgngobgcbagnjjddiojhdnbgoo"     # dérivé de la clé publique de web/extension/manifest.json
ORIGINE = f"chrome-extension://{ID_EXTENSION}"
DUREE_S = 120
EN_ATTENTE = {}            # jeton -> (expiration, données)
VERROU = threading.Lock()


def _purger(maintenant):
    for j in [j for j, (fin, _) in EN_ATTENTE.items() if fin < maintenant]:
        del EN_ATTENTE[j]


def deposer(donnees):
    """Garde les données pour l'extension ; renvoie le jeton à usage unique."""
    jeton = secrets.token_urlsafe(32)
    with VERROU:
        _purger(time.time())
        EN_ATTENTE[jeton] = (time.time() + DUREE_S, donnees)
    return jeton


def retirer(jeton, origine):
    """Données du jeton (retirées : un seul usage), seulement pour l'extension LMAgent ; sinon None."""
    if origine != ORIGINE:
        return None
    with VERROU:
        _purger(time.time())
        trouve = EN_ATTENTE.pop(jeton, None)
    return trouve[1] if trouve else None


SOURCE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "web" / "extension"


def dossier_extension():
    """Dossier à charger dans Chrome (« Charger l'extension non empaquetée »), dans les données de LMAgent : son chemin
    ne change pas d'une version à l'autre. Remis à jour depuis la version installée à chaque appel."""
    import emplacements
    cible = emplacements.dossier("extension_chrome")
    cible.mkdir(parents=True, exist_ok=True)
    for f in SOURCE.iterdir():
        if f.is_file() and (not (cible / f.name).exists() or (cible / f.name).read_bytes() != f.read_bytes()):
            shutil.copy2(f, cible / f.name)
    return cible


def ouvrir_dans_chrome(lien, jeton, port):
    """Ouvre la fiche dans un nouvel onglet du Chrome habituel ; l'extension remplit le formulaire."""
    import chrome
    exe = chrome.trouver_chrome()
    if not exe:
        raise chrome.ChromeIntrouvable("Google Chrome introuvable sur ce PC.")
    subprocess.Popen([str(exe), f"{lien.split('#')[0]}#lmagent={port}.{jeton}"], close_fds=True)
