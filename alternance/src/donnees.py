"""Emplacement des données personnelles : alternance/donnees/ (non versionné, sauf les modèles *.example.*).

Avant, ces fichiers étaient directement dans alternance/. Au premier lancement, ils sont déplacés
tout seuls dans alternance/donnees/ (sur chaque PC), et le chemin du tableau est corrigé dans la config.
Un fichier ouvert (le tableau dans Excel…) est laissé en place : il sera déplacé au lancement suivant.
"""
import json
import os
from pathlib import Path

ALTERNANCE = Path(__file__).resolve().parent.parent   # dossier alternance/
DONNEES = ALTERNANCE / "donnees"

PERSONNELS = ["config_alternance.json", "profil.md", "interdits.md", "reponses_lba.json",
              "entreprises_refusees.csv", "suivi_alternance.xlsx"]


def ranger():
    """Déplace les fichiers personnels de l'ancien emplacement (alternance/) vers alternance/donnees/."""
    DONNEES.mkdir(exist_ok=True)
    for nom in PERSONNELS:
        ancien, nouveau = ALTERNANCE / nom, DONNEES / nom
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
    _corriger_chemin_tableau()


def _corriger_chemin_tableau():
    """Le tableau est indiqué par un chemin complet dans la config : on le fait suivre s'il a été déplacé."""
    config = DONNEES / "config_alternance.json"
    if not config.exists():
        return
    try:
        cfg = json.loads(config.read_text(encoding="utf-8"))
    except Exception:
        return
    chemin = cfg.get("tableau_suivi") or ""
    reel = Path(os.path.expanduser(chemin)) if chemin else None
    if not reel or reel.exists() or reel.parent.resolve() != ALTERNANCE.resolve():
        return
    deplace = DONNEES / reel.name
    if deplace.exists():
        cfg["tableau_suivi"] = chemin.replace(reel.name, "donnees/" + reel.name) if chemin.endswith(reel.name) \
            else str(deplace)
        config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("   📁 Chemin du tableau mis à jour dans la config (alternance/donnees/)")


def chemin(nom):
    """Chemin d'un fichier personnel : alternance/donnees/<nom>, ou l'ancien emplacement s'il n'a pas pu être déplacé."""
    nouveau = DONNEES / nom
    ancien = ALTERNANCE / nom
    return ancien if (ancien.exists() and not nouveau.exists()) else nouveau
