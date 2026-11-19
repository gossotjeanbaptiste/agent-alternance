"""À la fin (appelé automatiquement) : modèle déchargé, LM Studio refermé et tour rendormie, mais seulement là où
c'est le script qui les a chargés, ouverts ou réveillés. Dans une boucle de passages, seul le dernier referme
(voir boucle.py) : les autres transmettent ce qui reste ouvert au passage suivant."""
import subprocess

import agent


def _reprendre_boucle():
    """Reprend ce que les passages précédents d'une boucle ont laissé ouvert (à refermer par le dernier)."""
    import boucle
    etat = boucle.reprendre()
    for x in etat.get("a_decharger", []):
        if tuple(x) not in agent.A_DECHARGER:
            agent.A_DECHARGER.append(tuple(x))
    agent.TOUR_REVEILLEE = agent.TOUR_REVEILLEE or bool(etat.get("tour_reveillee"))
    agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT = agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT or bool(etat.get("lmstudio_local"))
    if etat.get("lmstudio_tour"):
        try:
            import tour
            tour.LMSTUDIO_OUVERT_PAR_SCRIPT = True
        except ImportError:
            pass


def _garder_pour_le_passage_suivant():
    """Passage d'une boucle qui n'est pas le dernier : rien n'est fermé, le suivant reprend le tout."""
    import boucle
    if not boucle.garder_ouvert():
        return False
    try:
        import tour
        lmstudio_tour = bool(tour.LMSTUDIO_OUVERT_PAR_SCRIPT)
    except ImportError:
        lmstudio_tour = False
    boucle.transmettre({"a_decharger": [list(x) for x in agent.A_DECHARGER], "tour_reveillee": agent.TOUR_REVEILLEE,
                        "lmstudio_local": agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT, "lmstudio_tour": lmstudio_tour})
    agent.A_DECHARGER.clear()
    agent.say("⏭️ Modèle et LM Studio gardés ouverts pour le passage suivant")
    return True


def liberer_modele():
    """Décharge les modèles chargés par le script (appelé automatiquement à la fin).
    Dans une boucle de passages, seul le dernier passage referme (voir boucle.py)."""
    _reprendre_boucle()
    if _garder_pour_le_passage_suivant():
        return
    while agent.A_DECHARGER:
        genre, nom, base, inst = agent.A_DECHARGER.pop()
        try:
            if genre == "distant":
                agent._api(base, "POST", "/api/v1/models/unload", {"instance_id": inst}, timeout=60)
            else:
                agent._lms("unload", inst)
            agent.log(f"🧹 Modèle déchargé de {nom} (mémoire de la carte graphique libérée)")
            print(f"🧹 Modèle déchargé de {nom}")
        except Exception as e:
            agent.log(f"⚠️ Déchargement impossible sur {nom} : {e}")
    try:
        agent.npu.arreter()                  # OpenVINO (NPU), s'il a été lancé par le script
    except Exception as e:
        agent.log(f"⚠️ Arrêt d'OpenVINO impossible : {e}")
    agent.fermer_lmstudio()
    agent.remettre_tour_en_veille()


def fermer_lmstudio():
    """Ferme LM Studio là où c'est le script qui l'a ouvert (tour et/ou ce PC)."""
    try:
        import tour
        tour.fermer_lmstudio_si_ouvert(log=agent.say)
    except Exception as e:
        agent.log(f"⚠️ Fermeture de LM Studio sur la tour impossible : {e}")
    if agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT:
        agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT = False
        agent._lms("server", "stop", timeout=60)
        subprocess.run(["taskkill", "/IM", "Bionic.exe", "/F"], capture_output=True)
        agent.say("🧹 LM Studio fermé sur ce PC (il avait été ouvert par le script)")


def remettre_tour_en_veille():
    """Rendort la tour, mais seulement si c'est le script qui l'a réveillée
    (si tu l'utilisais déjà, on n'y touche pas)."""
    if not agent.TOUR_REVEILLEE or not agent.CONFIG.get("tour", {}).get("veille_apres", False):
        return
    agent.TOUR_REVEILLEE = False
    try:
        import tour
        agent.say("😴 Remise en veille de la tour...")
        tour.veille(log=agent.say)
    except Exception as e:
        agent.log(f"⚠️ Remise en veille impossible : {e}")
