"""Carte graphique de la tour déjà occupée (un jeu…) ? Lecture seule, par nvidia-smi via SSH."""
import subprocess

import tour
from tour import T, _print


def lire_gpu():
    """Mémoire et charge de la carte graphique de la tour (nvidia-smi par SSH, simple lecture).
    Renvoie {"libre_mo", "total_mo", "utilisation"} ou None si impossible à lire."""
    cible = tour._cible_ssh()
    if not cible:
        return None
    try:
        r = tour._ssh_brut(cible, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu "
                                  "--format=csv,noheader,nounits", timeout=20)
    except subprocess.TimeoutExpired:
        return None
    return analyser_nvidia_smi(r.stdout if r and r.returncode == 0 else "")


def analyser_nvidia_smi(sortie):
    """« 5120, 8188, 87 » -> {"libre_mo": 3068, "total_mo": 8188, "utilisation": 87}"""
    try:
        utilise, total, charge = [int(float(x)) for x in sortie.strip().splitlines()[0].split(",")[:3]]
        return {"libre_mo": total - utilise, "total_mo": total, "utilisation": charge}
    except Exception:
        return None


def gpu_occupe(log=_print):
    """Vrai si la carte graphique de la tour sert déjà à autre chose (un jeu, par exemple) :
    pas assez de mémoire libre pour le modèle, ou carte déjà très sollicitée.
    Dans ce cas on laisse la tour tranquille et le travail se fait sur ce PC."""
    if not T.get("verifier_gpu", True) or tour.modele_charge():
        return False  # vérification désactivée, ou modèle déjà en place : rien de plus à réserver
    g = tour.lire_gpu()
    if g is None:
        log("   ℹ️ Impossible de lire l'état de la carte graphique de la tour : on l'utilise quand même")
        return False
    raisons = []
    if g["libre_mo"] < T["vram_libre_min_mo"]:
        raisons.append(f"{g['libre_mo']} Mo libres sur {g['total_mo']} (il en faut {T['vram_libre_min_mo']})")
    if g["utilisation"] > T["gpu_utilisation_max"]:
        raisons.append(f"utilisée à {g['utilisation']} %")
    if raisons:
        log(f"   🎮 Carte graphique de la tour occupée ({', '.join(raisons)}) : un jeu tourne sans doute,"
            " on n'y touche pas et le travail se fait sur ce PC")
        return True
    return False
