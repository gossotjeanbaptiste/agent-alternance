"""Ce PC fait tourner le modèle : ses niveaux essayés dans l'ordre (carte graphique dédiée, NPU Intel, carte graphique
du processeur, processeur : voir local.py), LM Studio démarré si besoin ; envoi des requêtes, avec bascule sur le
niveau suivant si celui-ci lâche en cours de route."""
import json
import sys
import time
import urllib.error
import urllib.request

import agent


def _lmstudio_demarre():
    """URL du serveur LM Studio de ce PC (appli ouverte en arrière-plan et serveur démarré si besoin), ou None."""
    candidates = [f"http://localhost:{p}/v1" for p in (1234, 1235)]
    url = next((u for u in candidates if agent._reachable(u)), None)
    if url:
        return url
    if not agent.LMS.exists():
        agent.say("   LM Studio absent de ce PC : on passe au suivant")
        return None
    if not agent._lmstudio_ouvert() and agent.CONFIG.get("fermer_lmstudio_apres", True):
        agent.LMSTUDIO_OUVERT_PAR_SCRIPT = True  # « lms server start » va l'ouvrir : on le refermera à la fin
    agent.say("Démarrage du serveur LM Studio...")
    agent._lms("server", "start")
    time.sleep(3)
    return next((u for u in candidates if agent._reachable(u)), None)


def a_decharger_local():
    """Modèle chargé dans LM Studio, tel que liberation.py le décharge à la fin."""
    return agent.CONFIG["modele"]


def ensure_server(sauf=()):
    """Premier niveau de ce PC qui marche (dans l'ordre du réglage ordre_ce_pc), sauf ceux déjà lâchés."""
    for niveau, nom in agent.niveaux_locaux():
        if nom in sauf:
            continue
        url = agent.demarrer_local(niveau)
        if url:
            agent.BASE_URL, agent.SERVEUR = url, nom
            agent.say(f"🧠 Modèle utilisé : {agent.SERVEUR} ({agent.BASE_URL})")
            return
    agent.say("❌ Aucun moyen de faire tourner le modèle sur ce PC. Ouvre LM Studio ou lance : lms server start")
    sys.exit(1)


def post_chat(req_body):
    """Envoie une requête au modèle. Si le niveau lâche en cours de route, bascule une fois sur le suivant."""
    for essai in range(2):
        corps = agent.npu.adapter(req_body) if agent.MOTEUR == "openvino" else req_body
        req = urllib.request.Request(f"{agent.BASE_URL}/chat/completions", data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                return json.loads(resp.read())["choices"][0]["message"]
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if essai:
                raise
            agent.say(f"⚠️ {agent.SERVEUR} ne répond plus ({e}) : bascule sur le suivant")
            if agent.MOTEUR == "openvino":
                agent.npu.arreter()
            agent.ECARTES.append(agent.SERVEUR)       # les niveaux déjà lâchés ne sont pas réessayés
            agent.ensure_server(sauf=tuple(agent.ECARTES))
