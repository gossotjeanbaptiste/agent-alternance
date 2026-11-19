"""Ce PC fait tourner le modèle, en essayant dans l'ordre (réglage « ordre_ce_pc ») :
    carte_dediee    carte graphique dédiée NVIDIA / AMD / Intel Arc (LM Studio : CUDA ou Vulkan)
    npu             NPU Intel des Core Ultra (OpenVINO Model Server : la carte graphique et le processeur restent
                    libres, le PC reste utilisable pendant une routine)
    carte_integree  carte graphique du processeur (LM Studio : Vulkan)
    processeur      processeur seul (LM Studio : moteur CPU, aucune couche sur une carte graphique)
Un niveau absent de ce PC est sauté ; un niveau qui échoue (moteur manquant, chargement impossible) passe la main
au suivant. Identique sur les deux branches : la partie propre à chacune (ouvrir LM Studio) est agent._lmstudio_demarre."""
import agent

ORDRE = ["carte_dediee", "npu", "carte_integree", "processeur"]


def niveaux():
    """[(niveau, nom pour le journal)] présents sur ce PC, dans l'ordre réglé."""
    res = []
    for niveau in agent.CONFIG.get("ordre_ce_pc") or ORDRE:
        if niveau == "carte_dediee" and (carte := agent.carte_dediee()):
            res.append((niveau, f"ce PC (carte graphique {carte})"))
        elif niveau == "npu" and agent.npu_intel():
            res.append((niveau, "ce PC (NPU Intel)"))
        elif niveau == "carte_integree" and agent.carte_integree():
            res.append((niveau, "ce PC (carte graphique du processeur)"))
        elif niveau == "processeur":
            res.append((niveau, "ce PC (processeur)"))
        elif niveau not in ORDRE:
            agent.say(f"   ⚠️ « {niveau} » inconnu dans le réglage ordre_ce_pc (attendus : {', '.join(ORDRE)})")
    return res


def famille(niveau):
    """Famille de moteurs LM Studio du niveau : cuda (NVIDIA), vulkan (AMD, Intel), cpu."""
    if niveau == "carte_dediee":
        return "cuda" if "nvidia" in agent.carte_dediee().lower() else "vulkan"
    return "vulkan" if niveau == "carte_integree" else "cpu"


def demarrer(niveau):
    """URL du serveur prêt pour ce niveau, ou None (on passe au suivant)."""
    agent.MOTEUR = "openvino" if niveau == "npu" else "lmstudio"
    if niveau == "npu":
        return agent.npu.demarrer()
    return _lmstudio(niveau)


def _lmstudio(niveau):
    """LM Studio de ce PC avec le moteur du niveau ; le modèle chargé entièrement sur la carte graphique, ou
    entièrement sur le processeur."""
    c = agent.CONFIG
    url = agent._lmstudio_demarre()
    if not url or not agent.choisir_moteur(famille(niveau)):
        return None
    if c["modele"] in agent._lms("ps").stdout:
        return url
    gpu = "off" if niveau == "processeur" else "max"
    agent.say(f"   Chargement de {c['modele']} ({'processeur' if gpu == 'off' else 'carte graphique'})...")
    r = agent._lms("load", c["modele"], "--context-length", str(c["contexte"]), "--gpu", gpu, "-y")
    if r.returncode or c["modele"] not in agent._lms("ps").stdout:
        detail = ((r.stderr or r.stdout or "").strip().splitlines() or ["?"])[-1]
        agent.say(f"   ⚠️ Chargement impossible ({detail[:200]}) : on passe au suivant")
        return None
    if c.get("decharger_a_la_fin", True):
        agent.A_DECHARGER.append(agent.a_decharger_local())
    return url
