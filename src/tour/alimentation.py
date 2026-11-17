"""Veille, arrêt et redémarrage de la tour par SSH (jamais déclenchés sans demande)."""
import tour
from tour import _print


def veille(log=_print):
    return tour._ssh_action(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
        "Tour mise en veille", log)


def eteindre(delai=60, log=_print):
    return tour._ssh_action(f"shutdown /s /t {delai} /c 'Arrêt demandé à distance (lm_agent)'",
                            f"Arrêt de la tour dans {delai} s (annulable : python src\\tour annuler)", log)


def redemarrer(delai=60, log=_print):
    return tour._ssh_action(f"shutdown /r /t {delai} /c 'Redémarrage demandé à distance (lm_agent)'",
                            f"Redémarrage de la tour dans {delai} s (annulable : python src\\tour annuler)", log)


def annuler(log=_print):
    return tour._ssh_action("shutdown /a", "Arrêt / redémarrage annulé", log)
