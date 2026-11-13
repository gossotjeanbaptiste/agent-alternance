"""Chemins du projet ; rend importables les modules de l'agent et de la routine d'alternance."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # dossier lm_agent (web/src/chemins.py -> lm_agent)
ALT = ROOT / "alternance"
LOGS = ROOT / "logs"

for p in (ALT / "src", ALT, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(1, str(p))
