"""Authentification de l'interface : un seul compte (identifiant + mot de passe), créé au premier lancement.

- Le compte est gardé dans alternance/donnees/acces_interface.json (non versionné) : mot de passe haché
  (werkzeug, jamais en clair) et clé secrète des sessions (pour rester connecté après un redémarrage).
- Mot de passe oublié : supprimer ce fichier, la page de création du compte revient au prochain affichage.
- Tentatives répétées : après 5 échecs, une attente qui double à chaque nouvel échec (30 s, 60 s…).
"""
import json
import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

import chemins  # noqa: F401
import donnees

FICHIER = donnees.chemin("acces_interface.json")
LONGUEUR_MIN = 8
ESSAIS_LIBRES = 5
ECHECS = {"nb": 0, "jusqua": 0.0}   # en mémoire : remis à zéro au redémarrage de l'interface


def _lire():
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _ecrire(d):
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    FICHIER.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def compte_existe():
    d = _lire()
    return bool(d.get("identifiant") and d.get("mot_de_passe"))


def identifiant():
    return _lire().get("identifiant", "")


def cle_secrete():
    """Clé qui signe les cookies de session ; créée au besoin et gardée dans le fichier."""
    d = _lire()
    if not d.get("cle"):
        d["cle"] = secrets.token_hex(32)
        _ecrire(d)
    return d["cle"]


def _verifier_nouveau(ident, mdp, confirmation):
    if not ident or len(ident) > 60:
        return "Identifiant vide ou trop long."
    if len(mdp) < LONGUEUR_MIN:
        return f"Mot de passe trop court : au moins {LONGUEUR_MIN} caractères."
    if mdp != confirmation:
        return "Les deux mots de passe ne sont pas identiques."
    return None


def creer_compte(ident, mdp, confirmation):
    """Premier lancement seulement. Renvoie (ok, message)."""
    if compte_existe():
        return False, "Un compte existe déjà."
    ident = (ident or "").strip()
    erreur = _verifier_nouveau(ident, mdp or "", confirmation or "")
    if erreur:
        return False, erreur
    d = _lire()
    d.update(identifiant=ident, mot_de_passe=generate_password_hash(mdp), cle=d.get("cle") or secrets.token_hex(32))
    _ecrire(d)
    return True, "Compte créé."


def attente_restante():
    return max(0, int(ECHECS["jusqua"] - time.time() + 0.999))


def verifier(ident, mdp):
    """Renvoie (ok, message). Freine les essais répétés."""
    reste = attente_restante()
    if reste:
        return False, f"Trop d'essais : réessaie dans {reste} s."
    d = _lire()
    ok = (bool(d.get("mot_de_passe")) and secrets.compare_digest((ident or "").strip(), d.get("identifiant", ""))
          and check_password_hash(d["mot_de_passe"], mdp or ""))
    if ok:
        ECHECS.update(nb=0, jusqua=0.0)
        return True, "Connecté."
    ECHECS["nb"] += 1
    if ECHECS["nb"] >= ESSAIS_LIBRES:
        ECHECS["jusqua"] = time.time() + 30 * 2 ** (ECHECS["nb"] - ESSAIS_LIBRES)
    return False, "Identifiant ou mot de passe incorrect."


def changer_mot_de_passe(actuel, nouveau, confirmation):
    """Renvoie (ok, message). Change aussi la clé secrète : les autres sessions sont déconnectées."""
    d = _lire()
    if not d.get("mot_de_passe") or not check_password_hash(d["mot_de_passe"], actuel or ""):
        return False, "Mot de passe actuel incorrect."
    erreur = _verifier_nouveau(d["identifiant"], nouveau or "", confirmation or "")
    if erreur:
        return False, erreur
    d.update(mot_de_passe=generate_password_hash(nouveau), cle=secrets.token_hex(32))
    _ecrire(d)
    return True, "Mot de passe changé."
