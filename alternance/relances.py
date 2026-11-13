"""Uniquement le suivi : lit Outlook, met à jour le tableau (envois, réponses, adresses invalides)
et prépare les relances dues en brouillon. Ne cherche pas de nouvelles entreprises.

    python alternance\\relances.py            (ajoute --essai pour ne rien écrire)
    .\\planifier.ps1 -Tache relances -Heure 10:00
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import alternance  # noqa: E402

alternance.main("relances")
