"""Protections de l'interface : accessible uniquement depuis ce PC.

- l'en-tête Host doit être 127.0.0.1 ou localhost (protection « DNS rebinding ») ;
- toute action (POST) exige un jeton secret tiré au hasard à chaque démarrage, et une origine locale
  (empêche un site web ouvert dans ton navigateur d'envoyer des requêtes à l'interface).
"""
import secrets
import urllib.parse

from flask import abort, request

JETON = secrets.token_urlsafe(24)
LOCAUX = ("127.0.0.1", "localhost")


def proteger():
    if request.host.rsplit(":", 1)[0] not in LOCAUX:
        abort(403)
    if request.method == "POST":
        if request.headers.get("X-Jeton") != JETON:
            abort(403)
        origine = request.headers.get("Origin")
        if origine and urllib.parse.urlparse(origine).hostname not in LOCAUX:
            abort(403)
