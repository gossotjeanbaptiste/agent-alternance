"""Ce qui peut faire tourner le modèle sur ce PC : carte graphique dédiée, NPU Intel, carte graphique du processeur.

Le nom seul départage une carte dédiée d'une carte intégrée :
- NVIDIA : toujours dédiée (GeForce, RTX, Quadro…) ;
- AMD : dédiée si « RX », « Radeon Pro », « Radeon VII »… (« AMD Radeon(TM) Graphics », « Radeon 780M » : intégrées) ;
- Intel : dédiée si « Arc A770 », « Arc B580 », « Arc Pro A60 »… (« Intel(R) Arc(TM) Graphics » des Core Ultra,
  « Arc 140V », « Iris Xe », « UHD » : intégrées).
"""
import re
import subprocess

import agent

DEDIEE_AMD = re.compile(r"\bRX\s?\d|Radeon\s+Pro|Radeon\s+VII|FirePro|Instinct", re.I)
DEDIEE_INTEL = re.compile(r"Arc(\(TM\))?\s+(Pro\s+)?[AB]\d{2,3}\b", re.I)
INTEGREE = re.compile(r"intel|amd|radeon", re.I)


def est_dediee(nom):
    """Vrai pour une carte graphique dédiée (voir les règles en tête du fichier)."""
    n = nom.lower()
    if "nvidia" in n:
        return True
    if "amd" in n or "radeon" in n:
        return bool(DEDIEE_AMD.search(nom))
    if "intel" in n:
        return bool(DEDIEE_INTEL.search(nom))
    return False


def est_integree(nom):
    """Vrai pour la carte graphique d'un processeur Intel ou AMD (pas les écrans virtuels, Microsoft Basic…)."""
    return bool(INTEGREE.search(nom)) and not est_dediee(nom)


def carte_dediee():
    """Nom de la carte graphique dédiée de ce PC, ou "" s'il n'y en a pas."""
    return next((n for n in agent.cartes_graphiques() if est_dediee(n)), "")


def carte_integree():
    """Nom de la carte graphique du processeur, ou "" s'il n'y en a pas."""
    return next((n for n in agent.cartes_graphiques() if est_integree(n)), "")


def npu_intel():
    """Nom du NPU Intel (« Intel(R) AI Boost » des Core Ultra) s'il est présent et en état de marche, sinon ""."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-PnpDevice -FriendlyName '*AI Boost*' -Status OK -ErrorAction SilentlyContinue)"
                            ".FriendlyName"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return next((l.strip() for l in r.stdout.splitlines() if l.strip()), "")
