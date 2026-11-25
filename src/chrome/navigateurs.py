"""Navigateurs installés sur ce PC, proposés quand Google Chrome est absent (formulaire La Bonne Alternance).

Ceux bâtis sur Chromium (Edge, Brave, Vivaldi, Opera, Opera GX) se pilotent comme Chrome et acceptent l'extension
LMAgent : le formulaire y est prérempli.
Les autres (Firefox, navigateur par défaut) ouvrent seulement la page : la lettre est copiée, à coller à la main."""
import os
import subprocess
import webbrowser
from pathlib import Path

DEFAUT = "defaut"
# clé : (nom affiché, chemins sous Program Files / Program Files (x86) / AppData\Local, bâti sur Chromium)
NAVIGATEURS = {
    "edge": ("Microsoft Edge", [r"Microsoft\Edge\Application\msedge.exe"], True),
    "brave": ("Brave", [r"BraveSoftware\Brave-Browser\Application\brave.exe"], True),
    "vivaldi": ("Vivaldi", [r"Vivaldi\Application\vivaldi.exe"], True),
    "opera": ("Opera", [r"Programs\Opera\opera.exe", r"Opera\opera.exe"], True),
    "operagx": ("Opera GX", [r"Programs\Opera GX\opera.exe", r"Opera GX\opera.exe"], True),
    "firefox": ("Mozilla Firefox", [r"Mozilla Firefox\firefox.exe"], False),
}


def _bases():
    return [b for b in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                        os.environ.get("LOCALAPPDATA")) if b]


def chemin(cle):
    """Chemin de l'exe du navigateur cle, ou None s'il n'est pas installé."""
    if cle not in NAVIGATEURS:
        return None
    for base in _bases():
        for relatif in NAVIGATEURS[cle][1]:
            exe = Path(base) / relatif
            if exe.exists():
                return exe
    return None


# début du ProgId Windows du navigateur par défaut -> clé (le plus long d'abord : « Opera GX » avant « Opera »)
PROGID = [("Opera GX", "operagx"), ("MSEdge", "edge"), ("Brave", "brave"), ("Vivaldi", "vivaldi"),
          ("Opera", "opera"), ("Firefox", "firefox"), ("ChromeHTML", "chrome")]


def par_defaut():
    """Clé du navigateur par défaut de Windows (« chrome » compris), ou None si inconnu."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Shell\Associations"
                            r"\UrlAssociations\https\UserChoice") as k:
            progid = str(winreg.QueryValueEx(k, "ProgId")[0])
    except (ImportError, OSError):
        return None
    return next((cle for debut, cle in PROGID if progid.startswith(debut)), None)


def installes():
    """[{"cle", "nom", "prerempli"}] : navigateurs trouvés (celui par défaut en premier), puis toujours le
    navigateur par défaut de Windows."""
    defaut = par_defaut()
    out = [{"cle": cle, "nom": nom + (" (navigateur par défaut)" if cle == defaut else ""), "prerempli": chromium}
           for cle, (nom, _, chromium) in NAVIGATEURS.items() if chemin(cle)]
    out.sort(key=lambda n: n["cle"] != defaut)
    return out + [{"cle": DEFAUT, "nom": "Navigateur par défaut de Windows", "prerempli": chromium(defaut)}]


def nom(cle):
    return NAVIGATEURS[cle][0] if cle in NAVIGATEURS else "ton navigateur par défaut"


def chromium(cle):
    """Bâti sur Chromium (pilotable, extension LMAgent installable) ; le navigateur par défaut s'il l'est."""
    if cle == DEFAUT:
        cle = par_defaut()
    return cle == "chrome" or (cle in NAVIGATEURS and NAVIGATEURS[cle][2])


def reel(cle):
    """« defaut » remplacé par la clé du navigateur par défaut quand il est connu et trouvé sur le PC."""
    if cle == DEFAUT:
        d = par_defaut()
        if d in NAVIGATEURS and chemin(d):
            return d
    return cle


def pour_extension():
    """Clé du navigateur où installer l'extension LMAgent, Chrome absent : celui par défaut s'il est bâti sur
    Chromium, sinon le premier trouvé ; None s'il n'y en a aucun."""
    candidats = [n["cle"] for n in installes() if n["prerempli"] and n["cle"] != DEFAUT]
    return candidats[0] if candidats else None


def page_extensions(cle):
    """Adresse de la page des extensions (chacun a la sienne ; Opera GX partage celle d'Opera)."""
    return {"edge": "edge://extensions", "brave": "brave://extensions", "vivaldi": "vivaldi://extensions",
            "opera": "opera://extensions", "operagx": "opera://extensions"}.get(cle, "chrome://extensions")


def ouvrir_page(cle, url):
    """Ouvre url dans le navigateur cle (sans pilotage) ; navigateur par défaut si cle est inconnu ou absent."""
    exe = chemin(cle) if cle != DEFAUT else None
    if exe:
        subprocess.Popen([str(exe), url], close_fds=True)
    else:
        webbrowser.open(url)
