"""Protections de l'interface.

- l'en-tête Host doit être 127.0.0.1 ou localhost (protection « DNS rebinding ») ;
- toute action (POST) exige un jeton secret tiré au hasard à chaque démarrage, et une origine locale
  (empêche un site web ouvert dans ton navigateur d'envoyer des requêtes à l'interface) ;
- il faut être connecté (identifiant + mot de passe, voir auth.py) pour tout le reste que la page
  de connexion et les fichiers statiques (logo, style).
"""
import secrets
import urllib.parse

from flask import abort, jsonify, redirect, request, session

import auth

JETON = secrets.token_urlsafe(24)
LOCAUX = ("127.0.0.1", "localhost")
PUBLICS = {"static", "pages.connexion", "api.connexion"}   # accessibles sans être connecté
# accessibles pendant l'assistant de premier lancement (le reste y renvoie tant qu'il n'est pas terminé)
ASSISTANT = {"pages.assistant", "api.assistant", "api.assistant_cv", "api.deconnexion", "api.quitter"}


def connecte():
    """Vrai si la session correspond au compte actuel (un compte recréé invalide les anciennes sessions)."""
    ident = session.get("connecte")
    return bool(ident) and auth.compte_existe() and ident == auth.identifiant()


def proteger():
    if request.host.rsplit(":", 1)[0] not in LOCAUX:
        abort(403)
    if request.endpoint == "api.extension":     # extension Chrome : ses propres contrôles (extension_lba.py)
        return None
    if request.method == "POST":
        if request.headers.get("X-Jeton") != JETON:
            abort(403)
        origine = request.headers.get("Origin")
        if origine and urllib.parse.urlparse(origine).hostname not in LOCAUX:
            abort(403)
    if request.endpoint in PUBLICS:
        return None
    if connecte():
        import assistant
        if request.endpoint in ASSISTANT or not assistant.a_faire():
            return None
        if request.path.startswith("/api/"):
            return jsonify(ok=False, message="Termine d'abord l'assistant de premier lancement."), 409
        return redirect("/assistant")
    if request.path.startswith("/api/"):
        return jsonify(ok=False, message="Connexion requise.", connexion=True), 401
    suite = request.full_path.rstrip("?") if request.path != "/" else ""
    return redirect("/connexion" + (f"?suite={urllib.parse.quote(suite)}" if suite else ""))


def suite_sure(suite):
    """Page où revenir après la connexion : seulement un chemin de l'interface (pas un autre site)."""
    suite = suite or "/"
    return suite if suite.startswith("/") and not suite.startswith("//") and "\\" not in suite else "/"
