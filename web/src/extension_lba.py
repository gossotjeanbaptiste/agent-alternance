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
        if f.is_file() and f.name != "vue_le.txt" and (not (cible / f.name).exists() or (cible / f.name).read_bytes() != f.read_bytes()):
            shutil.copy2(f, cible / f.name)
    return cible


def _fichier_presence():
    import emplacements
    return emplacements.dossier("extension_chrome") / "vue_le.txt"


def noter_presence(origine):
    """L'extension se signale (installation, démarrage de Chrome) : rien n'est échangé, l'heure est seulement notée
    pour que la page À postuler dise « installée ». Vrai si c'est bien l'extension LMAgent."""
    if origine != ORIGINE:
        return False
    f = _fichier_presence()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    return True


def etat():
    """{"dossier", "vue_le"} pour la page À postuler : dossier à charger dans Chrome (remis à jour) et dernière fois
    que l'extension s'est signalée ("" si jamais : pas encore installée)."""
    try:
        dossier = str(dossier_extension())
    except OSError:
        dossier = ""
    try:
        vue = _fichier_presence().read_text(encoding="utf-8").strip()
    except OSError:
        vue = ""
    return {"dossier": dossier, "vue_le": vue}


def adresse(lien, jeton, port):
    """Adresse de la fiche avec le jeton que l'extension lit (puis efface)."""
    return f"{lien.split('#')[0]}#lmagent={port}.{jeton}"


def ouvrir_dans_chrome(lien, jeton, port, navigateur=None):
    """Ouvre la fiche dans un nouvel onglet du Chrome habituel (ou, Chrome absent, du navigateur choisi : Opera GX,
    Edge… où l'extension est installée) ; l'extension remplit le formulaire."""
    import chrome
    if navigateur:
        from chrome import navigateurs
        navigateurs.ouvrir_page(navigateur, adresse(lien, jeton, port))
        return
    exe = chrome.trouver_chrome()
    if not exe:
        raise chrome.ChromeIntrouvable("Google Chrome introuvable sur ce PC.")
    subprocess.Popen([str(exe), adresse(lien, jeton, port)], close_fds=True)
