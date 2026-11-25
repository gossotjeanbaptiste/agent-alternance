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
    lettres.py        lettres « À postuler » (fichier local et brouillons de la messagerie)
    parametres.py     page Paramètres : signature des candidatures par formulaire
    auth.py           compte de l'interface (identifiant + mot de passe haché), frein aux essais répétés
    relations.py      relations LinkedIn dans les entreprises du tableau
    theme.py          thème clair, sombre ou du système (réglage « interface.theme »)
    rapport*.py       page Rapport : bilan chiffré, rapport rédigé par le modèle (api_rapport.py)
    templates/        le HTML des pages        static/  style et JavaScript
"""
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from datetime import timedelta

from flask import Flask, session

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # modules de l'interface (web/src)
import auth  # noqa: E402
import chemins  # noqa: E402,F401
import securite  # noqa: E402
import theme  # noqa: E402
import tour_web  # noqa: E402
from api import api  # noqa: E402
from api_rapport import api_rapport  # noqa: E402
from pages import pages  # noqa: E402
from tableau import STATUTS  # noqa: E402

def alphabetique(liste):
    """Tri alphabétique à la française : sans tenir compte des accents ni des majuscules (« À postuler » avec les A)."""
    import unicodedata

    def cle(t):
        return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").casefold()
    return sorted(liste, key=cle)


HOTE, PORT = "127.0.0.1", 8765   # 127.0.0.1 = joignable uniquement depuis ce PC


def creer_app():
    import emplacements
    web = emplacements.RESSOURCES / "web"   # dans l'exe : fichiers extraits ; depuis le code : dossier web/
    app = Flask(__name__, template_folder=str(web / "templates"), static_folder=str(web / "static"))
    app.secret_key = auth.cle_secrete()   # signe le cookie de session (gardée : on reste connecté après un redémarrage)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30))
    app.before_request(securite.proteger)
    app.context_processor(lambda: {"jeton": securite.JETON, "avec_tour": tour_web.disponible(), "statuts": STATUTS, "statuts_tries": alphabetique(STATUTS),
                                   "connecte": session.get("connecte"), "theme": theme.attribut()})
    app.register_blueprint(pages)
    app.register_blueprint(api)
    app.register_blueprint(api_rapport)
    return app


def deja_lancee():
    """Vrai si une interface écoute déjà sur ce port (Windows laisserait en lancer une 2e en parallèle)."""
    try:
        with socket.create_connection((HOTE, PORT), timeout=1):
            return True
    except OSError:
        return False


def lancer_interface():
    """Démarre l'interface et ouvre le navigateur (ou ouvre celle qui tourne déjà)."""
    url = f"http://{HOTE}:{PORT}"
    if deja_lancee():
        print(f"L'interface tourne déjà : ouverture de {url} dans le navigateur.")
        webbrowser.open(url)
        return
    import emplacements
    import icone_tache
    print(f"Interface : {url}  (accessible uniquement depuis ce PC — bouton Quitter ou icône près de l'horloge)")
    icone_tache.demarrer(url, emplacements.RESSOURCES / "web" / "static" / "logo.png")
    import os
    if not os.environ.pop("LMAGENT_SANS_NAVIGATEUR", None):   # relancée après une mise à jour par git : page déjà ouverte
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        creer_app().run(host=HOTE, port=PORT, debug=False, use_reloader=False)
    except KeyboardInterrupt:            # Ctrl+C dans le terminal : quitté par l'utilisateur
        icone_tache.arreter()
        import veille_tour
        veille_tour.en_quittant()
    finally:
        icone_tache.arreter()


if __name__ == "__main__":
    lancer_interface()
