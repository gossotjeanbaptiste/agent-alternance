"""python src\\tour <commande> : pilotage de la tour en ligne de commande."""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
SRC = ICI.parent      # src/ : emplacements, et le paquet tour lui-même
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ICI]   # ses modules ne s'importent que par tour.
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tour  # noqa: E402

tour.main(sys.argv[1:])
