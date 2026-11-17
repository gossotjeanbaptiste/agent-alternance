"""Choix du moteur de LM Studio selon la carte graphique : NVIDIA -> CUDA le plus récent, AMD / Intel -> Vulkan,
sinon processeur."""
import re
import subprocess

import agent


def cartes_graphiques():
    """Noms des cartes graphiques de ce PC (Windows)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_VideoController).Name"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def type_gpu():
    """'nvidia', 'amd', 'intel' ou 'cpu' — la carte dédiée passe avant la carte intégrée."""
    noms = " | ".join(agent.cartes_graphiques()).lower()
    if "nvidia" in noms:
        return "nvidia"
    if "radeon" in noms or "amd" in noms:
        return "amd"
    if "intel" in noms and ("arc" in noms or "iris" in noms or "uhd" in noms):
        return "intel"
    return "cpu"


def _version(nom):
    """'llama.cpp-...@2.72.0' -> (2, 72, 0)"""
    v = nom.split("@")[-1] if "@" in nom else "0"
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _cuda(nom):
    """Version CUDA dans le nom du moteur : cuda13 -> 13, cuda12 -> 12, cuda -> 11 (ancien)."""
    m = re.search(r"nvidia-cuda(\d*)", nom)
    return int(m.group(1)[:2]) if m and m.group(1) else (11 if m else 0)


def _moteurs_installes():
    """Moteurs llama.cpp installés -> {nom@version: sélectionné?}"""
    res = {}
    for ligne in agent._lms("runtime", "ls").stdout.splitlines():
        m = re.match(r"\s*(llama\.cpp-\S+@\S+)", ligne)
        if m:
            res[m.group(1)] = "✓" in ligne
    return res


def _telecharger_cuda_recent():
    """Le CUDA le plus récent compatible avec ce PC (LM Studio vérifie le pilote), téléchargé s'il manque."""
    dispo = agent._lms("runtime", "get", "--list", "llama.cpp").stdout
    variantes = sorted(set(re.findall(r"llama\.cpp-win-x86_64-nvidia-cuda\d*-avx2", dispo)), key=_cuda)
    if variantes:
        cible = variantes[-1]
        if not any(n.startswith(cible + "@") for n in _moteurs_installes()):
            agent.say(f"   Téléchargement du moteur {cible} (CUDA {_cuda(cible)})...")
            agent._lms("runtime", "get", cible, "-y", timeout=1800)


def choisir_moteur():
    """Sélectionne dans LM Studio le meilleur moteur pour la carte graphique de ce PC."""
    voulu = agent.CONFIG.get("gpu", "auto")
    gpu = agent.type_gpu() if voulu == "auto" else voulu
    famille = {"nvidia": "cuda", "cuda": "cuda", "amd": "vulkan", "intel": "vulkan",
               "vulkan": "vulkan"}.get(gpu, "cpu")
    if famille == "cuda":
        _telecharger_cuda_recent()
    installes = _moteurs_installes()
    if famille == "cuda":
        candidats = [n for n in installes if "nvidia-cuda" in n]
        cle = lambda n: (_cuda(n), _version(n))  # noqa: E731
    elif famille == "vulkan":
        candidats = [n for n in installes if "vulkan" in n]
        cle = _version
    else:
        candidats = [n for n in installes if re.match(r"llama\.cpp-win-x86_64-avx2@", n)]
        cle = _version
    if not candidats:
        agent.say(f"   ⚠️ Aucun moteur {famille} installé dans LM Studio : on garde le moteur actuel "
                  "(installe-le dans LM Studio → Runtime)")
        return
    meilleur = max(candidats, key=cle)
    if installes.get(meilleur):
        agent.say(f"🎮 Carte graphique : {gpu} → moteur {meilleur} (déjà sélectionné)")
        return
    agent.say(f"🎮 Carte graphique : {gpu} → sélection du moteur {meilleur}")
    agent._lms("runtime", "select", meilleur)
    if agent.CONFIG["modele"] in agent._lms("ps").stdout:  # recharger avec le nouveau moteur
        agent._lms("unload", agent.CONFIG["modele"])
