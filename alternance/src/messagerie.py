"""Choix de la messagerie : Outlook classique (par défaut) ou IMAP (Gmail…).

    config_alternance.json -> "messagerie": {"type": "outlook"}   ou   {"type": "imap", "imap": {...}}
"""
from commun import CFG
from outlook import texte_mail  # noqa: F401  (marche pour les deux : mail Outlook ou IMAP)


def type_messagerie():
    return ((CFG.get("messagerie") or {}).get("type") or "outlook").lower()


def nom_messagerie():
    return "ta messagerie" if type_messagerie() == "imap" else "Outlook"


def ouvrir():
    """Objet messagerie : envois(), recus(), destinataires_brouillons(), programmes(), brouillon()…"""
    if type_messagerie() == "imap":
        from imap import Imap
        return Imap()
    from outlook import Outlook
    return Outlook()
