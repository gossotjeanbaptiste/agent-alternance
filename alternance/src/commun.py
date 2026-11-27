"""Réglages et outils partagés par tous les modules de la routine d'alternance."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # dossier alternance/
sys.path.insert(0, str(HERE.parent / "src"))    # modules de la racine du projet (src/agent/…)
import agent  # noqa: E402,F401  (connexion LM Studio, journal)
import donnees  # noqa: E402  (données personnelles : alternance/donnees/ ou %APPDATA%\LMAgent\donnees)

donnees.emplacements.ranger_au_demarrage()  # lancé depuis le code : racine du projet -> perso/
donnees.ranger()  # anciens emplacements (directement dans alternance/) -> alternance/donnees/
donnees.initialiser()  # installation neuve : config, profil et contre-prompt créés depuis les modèles
DONNEES = donnees.DONNEES
CFG = json.loads(donnees.chemin("config_alternance.json").read_text(encoding="utf-8"))
PROFIL = donnees.chemin("profil.md").read_text(encoding="utf-8")
INTERDITS = donnees.chemin("interdits.md")   # « contre-prompt » : ce que tu ne veux pas dans tes mails (facultatif)
DEPUIS = None   # date : ne lire les mails envoyés et reçus qu'à partir de ce jour (--depuis) ; None = fenêtre habituelle
ESSAI = False   # True avec --essai : rien n'est écrit (ni brouillon, ni Excel)
GARDE = None    # minuteur qui arrête tout si la lecture d'Outlook se bloque


def interdits():
    """Bloc à placer à la fin d'une consigne d'écriture : ce que tu ne veux surtout pas dans le texte
    (alternance/donnees/interdits.md, relu à chaque fois : une modification compte tout de suite).
    Les lignes vides et celles qui commencent par « # » ou « > » (titres, explications) sont ignorées."""
    try:
        lignes = INTERDITS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""
    regles = [l.strip() for l in lignes if l.strip() and not l.lstrip().startswith(("#", ">"))]
    if not regles:
        return ""
    return ("\n\nINTERDIT dans ce texte (consignes strictes du candidat, à respecter absolument) :\n"
            + "\n".join(r if r.startswith(("-", "*")) else "- " + r for r in regles) + "\n")


def P(p):
    """Chemin avec ~ développé."""
    return Path(os.path.expanduser(p))


def chemin_tableau():
    """Tableau de suivi : le chemin indiqué dans la config, sinon suivi_alternance.xlsx du dossier de données."""
    c = (CFG.get("tableau_suivi") or "").strip()
    return P(c) if c else donnees.chemin("suivi_alternance.xlsx")


_PJ_SIGNALEES = set()


def pieces_jointes():
    """Pièces jointes des candidatures (CV, calendrier…) : chemins de la config qui existent vraiment.
    Un chemin qui ne marche plus (config venue d'un autre PC…) est cherché par son nom dans le dossier
    pieces_jointes/ ; s'il reste introuvable, on le signale (une fois par lancement) au lieu de l'ignorer
    en silence, sinon le brouillon part sans CV sans que personne ne s'en aperçoive."""
    dossier = donnees.emplacements.dossier("pieces_jointes")
    ok = []
    for p in CFG.get("pieces_jointes") or []:
        chemin = P(p)
        if not chemin.is_file() and (dossier / chemin.name).is_file():
            chemin = dossier / chemin.name
        if chemin.is_file():
            ok.append(str(chemin))
        elif p not in _PJ_SIGNALEES:
            _PJ_SIGNALEES.add(p)
            say(f"   ⚠️ pièce jointe introuvable, le brouillon partira sans : {p} "
                f"(corrige le chemin dans Paramètres → Candidatures et relances → Fichiers ; tes fichiers sont dans {dossier})")
    if not ok and "_aucune" not in _PJ_SIGNALEES:
        _PJ_SIGNALEES.add("_aucune")
        say("   ⚠️ aucune pièce jointe utilisable : les candidatures partiront sans CV")
    return ok


def say(msg):
    agent.say(msg)


def etape(texte, detail="", k=None, n=None, ligne=None):
    """Étape en cours, affichée en direct par la page Routines (src/avancement.py). ligne : texte écrit aussi dans
    le journal de la routine (affiché seulement, pas noté dans le journal du jour : le Rapport ne le compte pas)."""
    if ligne:
        print(ligne, flush=True)
    try:
        import avancement
        avancement.etape(texte, detail, k, n)
    except Exception:
        pass


def lire_signature_html(f):
    """Contenu d'un fichier de signature (Outlook l'écrit en UTF-8 ou en windows-1252), sans ses balises de page.

    Une balise « <meta … charset=…> » collée au milieu d'un mail fait relire TOUT le mail dans le mauvais
    encodage par Outlook (lettre comprise : « �tudiant ») : on garde seulement le contenu de la signature.
    """
    import re
    b = f.read_bytes()
    try:
        texte = b.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = b.decode("cp1252", errors="replace")
    corps = re.search(r"<body[^>]*>(.*?)(?:</body>|$)", texte, flags=re.S | re.I)
    if corps:
        texte = corps.group(1)
    texte = re.sub(r"<head\b.*?</head>|<title\b.*?</title>", "", texte, flags=re.S | re.I)
    return re.sub(r"<!doctype[^>]*>|<meta\b[^>]*>|</?(?:html|head|body)\b[^>]*>", "", texte, flags=re.I).strip()


def signature_mail(fichier=None):
    """Signature HTML à mettre sous les mails, ou "" si "ajouter_signature" est à false.

    Prend le fichier HTML indiqué s'il existe (signature Outlook, ou imap.signature_html), sinon
    construit la signature à partir de "signature_formulaire" (nom, titre, téléphone, mail, liens).
    Lu à chaque brouillon : un changement fait dans la page Paramètres compte tout de suite.
    """
    if not CFG.get("ajouter_signature", False):
        return ""
    if fichier and P(fichier).is_file():
        return lire_signature_html(P(fichier))
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
