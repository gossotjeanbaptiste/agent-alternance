"""
Interface web locale de lm_agent — accessible UNIQUEMENT depuis ce PC.

    python web\\app.py      (le navigateur s'ouvre tout seul sur http://127.0.0.1:8765)

Organisation (modules dans web/src/) :
    app.py            démarrage du serveur (ce fichier, seul à la racine de web/)
    securite.py       accès réservé à ce PC, jeton contre les requêtes venues d'autres sites
    chemins.py        chemins du projet
    pages.py          les pages affichées
    api.py            les actions (changer un statut, lancer une routine, piloter la tour)
    suivi_donnees.py  lecture du tableau, statistiques, modification d'une ligne
    routines.py       lancement des routines en arrière-plan
    tour_web.py       état et pilotage de la tour
    lettres.py        lettres « À postuler » lues dans Outlook
    relations.py      relations LinkedIn dans les entreprises du tableau
    templates/        le HTML des pages        static/  style et JavaScript
"""
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # modules de l'interface (web/src)
import chemins  # noqa: E402,F401
import securite  # noqa: E402
import tour_web  # noqa: E402
from api import api  # noqa: E402
from pages import pages  # noqa: E402
from tableau import STATUTS  # noqa: E402

HOTE, PORT = "127.0.0.1", 8765   # 127.0.0.1 = joignable uniquement depuis ce PC


def creer_app():
    app = Flask(__name__)
    app.before_request(securite.proteger)
    app.context_processor(lambda: {"jeton": securite.JETON, "avec_tour": tour_web.disponible(), "statuts": STATUTS})
    app.register_blueprint(pages)
    app.register_blueprint(api)
    return app


def deja_lancee():
    """Vrai si une interface écoute déjà sur ce port (Windows laisserait en lancer une 2e en parallèle)."""
    try:
        with socket.create_connection((HOTE, PORT), timeout=1):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    url = f"http://{HOTE}:{PORT}"
    if deja_lancee():
        print(f"L'interface tourne déjà : ouverture de {url} dans le navigateur.")
        webbrowser.open(url)
        sys.exit(0)
    print(f"Interface : {url}  (accessible uniquement depuis ce PC — bouton Quitter pour arrêter)")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    creer_app().run(host=HOTE, port=PORT, debug=False, use_reloader=False)
