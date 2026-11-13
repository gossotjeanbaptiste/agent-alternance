"""Icône de la zone de notification (près de l'horloge) : montre que LMAgent tourne, permet de l'ouvrir ou de le quitter."""
import os
import threading
import webbrowser

ICONE = {"objet": None}


def demarrer(url, image, journal=print):
    """Affiche l'icône dans un fil à part. Renvoie l'icône, ou None si pystray / Pillow manquent."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        journal("Icône de notification indisponible : pystray ou Pillow n'est pas installé "
                "(python -m pip install -r requirements.txt).")
        return None
    menu = pystray.Menu(
        pystray.MenuItem("Ouvrir LMAgent", lambda: webbrowser.open(url), default=True),
        pystray.MenuItem("Quitter LMAgent", lambda: quitter()),
    )
    icone = pystray.Icon("LMAgent", Image.open(image), "LMAgent", menu)
    threading.Thread(target=icone.run, daemon=True).start()
    ICONE["objet"] = icone
    return icone


def arreter():
    """Retire l'icône (sinon elle reste affichée jusqu'au survol de la souris).
    visible = False la retire tout de suite (stop() ne fait que poster un message : os._exit passerait avant)."""
    icone, ICONE["objet"] = ICONE["objet"], None
    if icone is None:
        return
    for action in (lambda: setattr(icone, "visible", False), icone.stop):
        try:
            action()
        except Exception:
            pass


def quitter(code=0):
    """Ferme LMAgent (serveur web compris) ; une routine lancée continue dans son propre processus."""
    arreter()
    os._exit(code)
