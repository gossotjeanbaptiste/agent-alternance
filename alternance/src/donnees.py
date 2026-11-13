"""Emplacement des données personnelles : alternance/donnees/ (non versionné, sauf les modèles *.example.*).

Avant, ces fichiers étaient directement dans alternance/. Au premier lancement, ils sont déplacés
tout seuls dans alternance/donnees/ (sur chaque PC), et le chemin du tableau est corrigé dans la config.
Un fichier ouvert (le tableau dans Excel…) est laissé en place : il sera déplacé au lancement suivant.

Variable d'environnement LMAGENT_DONNEES : utilise un autre dossier de données (les tests s'en servent
pour ne jamais toucher aux vraies données) ; dans ce cas, aucun rangement n'est fait. Même chose pour la
version installée : ses données sont dans %APPDATA%/LMAgent/donnees (voir emplacements.py).
"""
import json
import os
from pathlib import Path

import emplacements  # noqa: E402  (racine du projet sur le chemin : voir commun.py)

ALTERNANCE = Path(__file__).resolve().parent.parent   # dossier alternance/
AUTRE = os.environ.get("LMAGENT_DONNEES") or (None if emplacements.DEPUIS_LE_CODE else str(emplacements.donnees()))
DONNEES = Path(AUTRE) if AUTRE else emplacements.donnees()

PERSONNELS = ["config_alternance.json", "profil.md", "interdits.md", "reponses_lba.json",
              "entreprises_refusees.csv", "suivi_alternance.xlsx"]


def ranger(alternance=None, donnees=None):
    """Déplace les fichiers personnels de l'ancien emplacement (alternance/) vers alternance/donnees/."""
    if AUTRE and alternance is None:
        DONNEES.mkdir(parents=True, exist_ok=True)
        return  # dossier de données imposé (tests) : on ne touche à rien d'autre
    alternance, donnees = alternance or ALTERNANCE, donnees or DONNEES
    donnees.mkdir(exist_ok=True)
    for nom in PERSONNELS:
        ancien, nouveau = alternance / nom, donnees / nom
        if ancien.exists() and not nouveau.exists():
            try:
                ancien.rename(nouveau)
                print(f"   📁 {nom} rangé dans alternance/donnees/")
            except OSError:
                print(f"   ⚠️ {nom} est ouvert (Excel ?) : laissé dans alternance/, rangé au prochain lancement")
        elif ancien.exists() and nouveau.exists():
            # ex. une interface lancée avant le rangement a réécrit l'ancien fichier
            print(f"   ⚠️ {nom} existe en double : alternance/donnees/{nom} est utilisé, "
                  f"alternance/{nom} est ignoré (compare-les puis supprime l'ancien)")
    _corriger_chemin_tableau(alternance, donnees)


A_CREER = {"config_alternance.json": "config_alternance.example.json", "profil.md": "profil.example.md",
           "interdits.md": "interdits.example.md"}


def initialiser(donnees=None):
    """Installation neuve : crée la config, le profil et le contre-prompt à partir des modèles d'exemple
    (l'assistant de premier lancement les remplit ensuite). Ne remplace jamais un fichier existant."""
    import shutil
    donnees = donnees or DONNEES
    donnees.mkdir(parents=True, exist_ok=True)
    crees = []
    for nom, modele in A_CREER.items():
        cible, source = donnees / nom, emplacements.modeles() / modele
        if not cible.exists() and source.exists():
            shutil.copy(source, cible)
            crees.append(nom)
    return crees


def _corriger_chemin_tableau(alternance=None, donnees=None):
    """Le tableau est indiqué par un chemin complet dans la config : on le fait suivre s'il a été déplacé."""
    alternance, donnees = alternance or ALTERNANCE, donnees or DONNEES
    config = donnees / "config_alternance.json"
    if not config.exists():
        return
    try:
        cfg = json.loads(config.read_text(encoding="utf-8"))
    except Exception:
        return
    chemin_tableau = cfg.get("tableau_suivi") or ""
    reel = Path(os.path.expanduser(chemin_tableau)) if chemin_tableau else None
    if not reel or reel.exists() or reel.parent.resolve() != alternance.resolve():
        return
    deplace = donnees / reel.name
    if deplace.exists():
        cfg["tableau_suivi"] = chemin_tableau.replace(reel.name, "donnees/" + reel.name) \
            if chemin_tableau.endswith(reel.name) else str(deplace)
        config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("   📁 Chemin du tableau mis à jour dans la config (alternance/donnees/)")


def chemin(nom, alternance=None, donnees=None):
    """Chemin d'un fichier personnel : alternance/donnees/<nom>, ou l'ancien emplacement s'il n'a pas pu être déplacé."""
    if AUTRE and alternance is None:
        return DONNEES / nom
    alternance, donnees = alternance or ALTERNANCE, donnees or DONNEES
    nouveau, ancien = donnees / nom, alternance / nom
    return ancien if (ancien.exists() and not nouveau.exists()) else nouveau
