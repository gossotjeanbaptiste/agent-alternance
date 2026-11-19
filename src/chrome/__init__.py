"""Pilotage de Google Chrome sans dépendance (protocole DevTools de Chrome) : ouvrir une page dans une fenêtre
de Chrome qui reste ouverte, y exécuter du JavaScript, joindre un fichier à un champ.

Chrome est lancé avec un profil à lui (dossier « chrome » des données de LMAgent) : il ne gêne pas le Chrome
habituel, et la fenêtre reste ouverte quand LMAgent a fini (c'est l'utilisateur qui relit et envoie).

    websocket.py   client WebSocket minimal (bibliothèque standard)
    session.py     lancement de Chrome, onglet piloté (evaluer, attendre, joindre un fichier)
"""
from .session import ChromeIntrouvable, Onglet, ouvrir, trouver_chrome  # noqa: F401
