"""À la fin (appelé automatiquement) : modèle déchargé et LM Studio refermé, seulement si c'est le script qui les a
chargés ou ouverts. Dans une boucle de passages, seul le dernier referme (voir boucle.py) : les autres transmettent
ce qui reste ouvert au passage suivant."""
import subprocess

import agent


def _reprendre_boucle():
    """Reprend ce que les passages précédents d'une boucle ont laissé ouvert (à refermer par le dernier)."""
    import boucle
    etat = boucle.reprendre()
    for m in etat.get("a_decharger", []):
        if m not in agent.A_DECHARGER:
            agent.A_DECHARGER.append(m)
    agent.LMSTUDIO_OUVERT_PAR_SCRIPT = agent.LMSTUDIO_OUVERT_PAR_SCRIPT or bool(etat.get("lmstudio_local"))


def _garder_pour_le_passage_suivant():
    """Passage d'une boucle qui n'est pas le dernier : rien n'est fermé, le suivant reprend le tout."""
    import boucle
    if not boucle.garder_ouvert():
        return False
    boucle.transmettre({"a_decharger": list(agent.A_DECHARGER), "lmstudio_local": agent.LMSTUDIO_OUVERT_PAR_SCRIPT})
    agent.A_DECHARGER.clear()
    agent.say("⏭️ Modèle et LM Studio gardés ouverts pour le passage suivant")
    return True


def liberer_modele():
    """Décharge le modèle s'il a été chargé par le script (appelé automatiquement à la fin).
    Dans une boucle de passages, seul le dernier passage referme (voir boucle.py)."""
    _reprendre_boucle()
    if _garder_pour_le_passage_suivant():
        return
    while agent.A_DECHARGER:
        m = agent.A_DECHARGER.pop()
        try:
            agent._lms("unload", m, timeout=120)
            agent.log("🧹 Modèle déchargé (mémoire de la carte graphique libérée)")
            print("🧹 Modèle déchargé")
        except Exception as e:
            agent.log(f"⚠️ Déchargement impossible : {e}")
    try:
        agent.npu.arreter()                  # OpenVINO (NPU), s'il a été lancé par le script
    except Exception as e:
        agent.log(f"⚠️ Arrêt d'OpenVINO impossible : {e}")
    if agent.LMSTUDIO_OUVERT_PAR_SCRIPT:
        agent.LMSTUDIO_OUVERT_PAR_SCRIPT = False
        agent._lms("server", "stop", timeout=60)
        subprocess.run(["taskkill", "/IM", "Bionic.exe", "/F"], capture_output=True)
        agent.log("🧹 LM Studio fermé (il avait été ouvert par le script)")
        print("🧹 LM Studio fermé")
