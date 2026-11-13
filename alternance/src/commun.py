"""Réglages et outils partagés par tous les modules de la routine d'alternance."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # dossier alternance/ (config, profil, tableau)
sys.path.insert(0, str(HERE.parent))            # racine du projet (agent.py)
import agent  # noqa: E402,F401  (connexion LM Studio, journal)

CFG = json.loads((HERE / "config_alternance.json").read_text(encoding="utf-8"))
PROFIL = (HERE / "profil.md").read_text(encoding="utf-8")
ESSAI = False   # True avec --essai : rien n'est écrit (ni brouillon, ni Excel)
GARDE = None    # minuteur qui arrête tout si la lecture d'Outlook se bloque


def P(p):
    """Chemin avec ~ développé."""
    return Path(os.path.expanduser(p))


def say(msg):
    agent.say(msg)


def signature_mail(fichier=None):
    """Signature HTML à mettre sous les mails, ou "" si "ajouter_signature" est à false.

    Prend le fichier HTML indiqué s'il existe (signature Outlook, ou imap.signature_html), sinon
    construit la signature à partir de "signature_formulaire" (nom, titre, téléphone, mail, liens).
    Lu à chaque brouillon : un changement fait dans la page Paramètres compte tout de suite.
    """
    if not CFG.get("ajouter_signature", False):
        return ""
    if fichier and P(fichier).is_file():
        return P(fichier).read_text(encoding="utf-8", errors="replace")
    from html import escape
    s = CFG.get("signature_formulaire") or {}
    lignes = [f"<b>{escape(s['nom'])}</b>" if s.get("nom") else ""]
    lignes += [escape(s.get(c) or "") for c in ("titre", "telephone", "email")]
    for etiquette, cle in (("LinkedIn", "linkedin"), ("Portfolio", "portfolio"), ("GitHub", "github")):
        if s.get(cle):
            u = escape(s[cle])
            lignes.append(f"{etiquette} : <a href='{u}'>{u}</a>")
    lignes = [l for l in lignes if l]
    if not lignes:
        return ""
    return ("<div style='font-family:Calibri,Arial,sans-serif;font-size:11pt'>"
            + "<br>".join(lignes) + "</div>")
