"""Lancement de Chrome (profil à part, port de débogage local) et onglet piloté par le protocole DevTools."""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import emplacements
from .websocket import WebSocket

PORT = 9333   # port de débogage, seulement sur 127.0.0.1


class ChromeIntrouvable(RuntimeError):
    pass


def trouver_chrome():
    """Chemin de chrome.exe (installation pour tous ou pour l'utilisateur), ou None."""
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            exe = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if exe.exists():
                return exe
    return None


def _json(chemin, methode="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{chemin}", method=methode)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def _chrome_pret():
    try:
        _json("/json/version")
        return True
    except Exception:
        return False


def _lancer():
    exe = trouver_chrome()
    if not exe:
        raise ChromeIntrouvable("Google Chrome introuvable sur ce PC : installe-le, ou remplis le formulaire à la main.")
    profil = emplacements.dossier("chrome")
    profil.mkdir(parents=True, exist_ok=True)
    # fenêtre normale (pas de CREATE_NO_WINDOW pour une appli à fenêtre), qui survit à LMAgent
    subprocess.Popen([str(exe), f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                      f"--user-data-dir={profil}", "--no-first-run", "--no-default-browser-check", "about:blank"],
                     close_fds=True)
    for _ in range(40):
        if _chrome_pret():
            return
        time.sleep(0.5)
    raise ChromeIntrouvable("Chrome ne répond pas sur son port de pilotage : ferme les fenêtres Chrome de LMAgent et réessaie.")


def ouvrir(url):
    """Ouvre url dans un nouvel onglet du Chrome de LMAgent (lancé si besoin) ; renvoie l'onglet piloté."""
    if not _chrome_pret():
        _lancer()
    cible = _json(f"/json/new?{url}", methode="PUT")
    return Onglet(cible["webSocketDebuggerUrl"], cible["id"])


class Onglet:
    def __init__(self, ws_url, id_cible):
        self.id = id_cible
        self.ws = WebSocket(ws_url)
        self._n = 0

    def commande(self, methode, **params):
        """Envoie une commande DevTools et attend sa réponse (les événements reçus entre-temps sont ignorés)."""
        self._n += 1
        n = self._n
        self.ws.envoyer(json.dumps({"id": n, "method": methode, "params": params}))
        while True:
            r = json.loads(self.ws.recevoir())
            if r.get("id") == n:
                if "error" in r:
                    raise RuntimeError(f"{methode} : {r['error'].get('message')}")
                return r.get("result", {})

    def evaluer(self, js):
        """Valeur d'une expression JavaScript dans la page (les promesses sont attendues)."""
        r = self.commande("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text") or "erreur JavaScript")
        return (r.get("result") or {}).get("value")

    def attendre(self, js, delai=20, pas=0.5):
        """Attend que l'expression JavaScript soit vraie ; renvoie sa valeur, ou None après le délai."""
        fin = time.time() + delai
        while time.time() < fin:
            try:
                v = self.evaluer(js)
            except RuntimeError:
                v = None
            if v:
                return v
            time.sleep(pas)
        return None

    def joindre(self, selecteur, chemin):
        """Joint un fichier du PC au champ <input type=file> désigné par le sélecteur CSS."""
        racine = self.commande("DOM.getDocument", depth=-1, pierce=True)["root"]["nodeId"]
        noeud = self.commande("DOM.querySelector", nodeId=racine, selector=selecteur).get("nodeId")
        if not noeud:
            raise RuntimeError(f"champ de fichier introuvable ({selecteur})")
        self.commande("DOM.setFileInputFiles", nodeId=noeud, files=[str(chemin)])

    def montrer(self):
        """Met l'onglet au premier plan."""
        try:
            _json(f"/json/activate/{self.id}")
        except Exception:
            pass

    def fermer(self):
        self.ws.fermer()
