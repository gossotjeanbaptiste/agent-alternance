"""Page « Paramètres » : signature des candidatures par formulaire (La Bonne Alternance, site de l'entreprise)
et choix d'ajouter ou non une signature sous les mails.

Les valeurs sont écrites dans alternance/donnees/config_alternance.json (non versionné) et appliquées
tout de suite au serveur web (sans le redémarrer).
"""
import json

import chemins  # noqa: F401
import commun
import lettres

FICHIER = commun.donnees.chemin("config_alternance.json")

# (clé, libellé, exemple)
CHAMPS = [
    ("nom", "Nom", "Prénom NOM"),
    ("titre", "Titre", "Étudiant en … à …, en recherche d'alternance"),
    ("telephone", "Téléphone", "+33 6 00 00 00 00"),
    ("email", "Adresse mail", "prenom.nom@exemple.fr"),
    ("linkedin", "LinkedIn", "https://www.linkedin.com/in/…"),
    ("portfolio", "Portfolio", "https://…"),
    ("github", "GitHub", "https://github.com/…"),
]


def lire():
    s = commun.CFG.get("signature_formulaire") or {}
    return {cle: str(s.get(cle) or "") for cle, _, _ in CHAMPS}, str(commun.CFG.get("debut_signature") or "")


def ajouter_signature():
    """(case cochée ?, fichier HTML de signature utilisé à la place de la signature construite, ou "")."""
    c = commun.CFG
    m = c.get("messagerie") or {}
    f = (m.get("imap") or {}).get("signature_html") if m.get("type", "outlook") == "imap" else c.get("signature_html")
    return bool(c.get("ajouter_signature", False)), (f if f and commun.P(f).is_file() else "")


def lire_interdits():
    """Texte du « contre-prompt » (alternance/donnees/interdits.md), ou le modèle s'il n'existe pas encore."""
    for f in (commun.INTERDITS, commun.DONNEES / "interdits.example.md"):
        if f.exists():
            return f.read_text(encoding="utf-8")
    return ""


def enregistrer_interdits(texte):
    """Écrit alternance/donnees/interdits.md ; relu à chaque mail écrit par le modèle. Renvoie (ok, message)."""
    try:
        commun.INTERDITS.write_text(str(texte or "")[:20000].replace("\r\n", "\n"), encoding="utf-8")
    except Exception as e:
        return False, f"Écriture impossible : {e}"
    n = commun.interdits().count("\n- ")
    return True, f"Enregistré : {n} interdiction(s) ajoutée(s) aux consignes des prochains mails."


def enregistrer(signature, debut, ajouter=None):
    """Écrit la signature dans la config ; renvoie (ok, message)."""
    propre = {cle: str(signature.get(cle) or "").strip()[:300] for cle, _, _ in CHAMPS}
    try:
        cfg = json.loads(FICHIER.read_text(encoding="utf-8"))  # relu : on ne touche qu'à ces deux réglages
    except Exception as e:
        return False, f"Lecture de config_alternance.json impossible : {e}"
    cfg["signature_formulaire"] = propre
    cfg["debut_signature"] = str(debut or "").strip()[:200]
    if ajouter is not None:
        cfg["ajouter_signature"] = bool(ajouter)
    try:
        FICHIER.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return False, f"Écriture impossible : {e}"
    commun.CFG["signature_formulaire"] = propre          # pris en compte tout de suite
    commun.CFG["debut_signature"] = cfg["debut_signature"]
    if ajouter is not None:
        commun.CFG["ajouter_signature"] = bool(ajouter)
    lettres.CACHE["quand"] = 0                           # la page « À postuler » relira la signature
    return True, "Signature enregistrée."
