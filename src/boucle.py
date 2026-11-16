"""Passages d'une même boucle (routine lancée N fois d'affilée) : le modèle et LM Studio restent ouverts entre les
passages, seul le dernier referme ce que le script a ouvert.

lmagent.routine (la boucle) donne à chaque passage :
- LMAGENT_BOUCLE        identifiant de la boucle (nom du fichier d'état) ;
- LMAGENT_GARDER_OUVERT "1" pour tous les passages sauf le dernier.

Un passage qui garde tout ouvert note dans le fichier d'état ce que le script a ouvert (modèle à décharger,
LM Studio ouvert…) ; le passage suivant le reprend à son compte, et le dernier referme le tout.
"""
import json
import os

import emplacements


def fichier():
    """Fichier d'état de la boucle en cours, ou None hors boucle."""
    ident = os.environ.get("LMAGENT_BOUCLE")
    if not ident:
        return None
    return emplacements.dossier("taches") / f"boucle_{ident}.json"


def garder_ouvert():
    """Vrai pour un passage qui n'est pas le dernier de sa boucle."""
    return fichier() is not None and os.environ.get("LMAGENT_GARDER_OUVERT") == "1"


def reprendre():
    """Ce que les passages précédents ont laissé ouvert ({} s'il n'y a rien) ; le fichier est supprimé."""
    f = fichier()
    if f is None or not f.exists():
        return {}
    try:
        etat = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        etat = {}
    f.unlink(missing_ok=True)
    return etat if isinstance(etat, dict) else {}


def transmettre(etat):
    """Laisse au passage suivant ce que ce passage garde ouvert."""
    f = fichier()
    if f is None:
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")


def environnement(ident, passage, total):
    """Variables d'environnement d'un passage (passage compté à partir de 1)."""
    return {**os.environ, "LMAGENT_BOUCLE": str(ident), "LMAGENT_GARDER_OUVERT": "1" if passage < total else "0"}


def nettoyer(ident):
    """Fin de boucle : supprime un fichier d'état resté là (dernier passage arrêté de force)."""
    (emplacements.dossier("taches") / f"boucle_{ident}.json").unlink(missing_ok=True)
