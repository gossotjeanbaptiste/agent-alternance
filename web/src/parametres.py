"""Page « Paramètres » : signature des candidatures par formulaire (La Bonne Alternance, site de l'entreprise).

Les valeurs sont écrites dans alternance/config_alternance.json (non versionné) et appliquées
tout de suite au serveur web (sans le redémarrer).
"""
import json

import chemins  # noqa: F401
import commun
import lettres

FICHIER = commun.HERE / "config_alternance.json"

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


def enregistrer(signature, debut):
    """Écrit la signature dans la config ; renvoie (ok, message)."""
    propre = {cle: str(signature.get(cle) or "").strip()[:300] for cle, _, _ in CHAMPS}
    try:
        cfg = json.loads(FICHIER.read_text(encoding="utf-8"))  # relu : on ne touche qu'à ces deux réglages
    except Exception as e:
        return False, f"Lecture de config_alternance.json impossible : {e}"
    cfg["signature_formulaire"] = propre
    cfg["debut_signature"] = str(debut or "").strip()[:200]
    try:
        FICHIER.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return False, f"Écriture impossible : {e}"
    commun.CFG["signature_formulaire"] = propre          # pris en compte tout de suite
    commun.CFG["debut_signature"] = cfg["debut_signature"]
    lettres.CACHE["quand"] = 0                           # la page « À postuler » relira la signature
    return True, "Signature enregistrée."
