"""Uniquement la recherche : trouve de nouvelles entreprises (liste « À contacter », alertes
LinkedIn, La Bonne Alternance), écrit les candidatures en brouillon et les ajoute au tableau.
Ne touche pas au suivi ni aux relances.

    python alternance\\recherche.py           (ajoute --essai pour ne rien écrire)
    .\\outils\\planifier.ps1 (ou page Routines de l'interface) -Tache recherche -Heure 10:30
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import alternance  # noqa: E402

alternance.main("recherche")
