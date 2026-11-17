"""LM Studio de ce PC : serveur démarré (appli ouverte si besoin), moteur choisi, modèle chargé ; envoi des requêtes."""
import json
import sys
import time
import urllib.request

import agent


def ensure_server():
    """Démarre le serveur LM Studio de ce PC, choisit le moteur et charge le modèle."""
    c = agent.CONFIG
    candidates = [f"http://localhost:{p}/v1" for p in (1234, 1235)]
    url = next((u for u in candidates if agent._reachable(u)), None)
    if not url and not agent._lmstudio_ouvert() and c.get("fermer_lmstudio_apres", True):
        agent.LMSTUDIO_OUVERT_PAR_SCRIPT = True  # « lms server start » va l'ouvrir : on le refermera à la fin
    if not url:
        agent.say("Démarrage du serveur LM Studio...")
        agent._lms("server", "start")
        time.sleep(3)
        url = next((u for u in candidates if agent._reachable(u)), None)
        if not url:
            agent.say("❌ Serveur LM Studio injoignable. Ouvre LM Studio ou lance : lms server start")
            sys.exit(1)
    agent.BASE_URL = url
    agent.choisir_moteur()
    if c["modele"] not in agent._lms("ps").stdout:
        agent.say(f"   Chargement de {c['modele']} (toutes les couches sur la carte graphique)...")
        t = time.time()
        agent._lms("load", c["modele"], "--context-length", str(c["contexte"]), "--gpu", "max", "-y")
        agent.say(f"   Modèle chargé en {time.time() - t:.0f} s")
        if c.get("decharger_a_la_fin", True):
            agent.A_DECHARGER.append(c["modele"])
    agent.say(f"🧠 Modèle prêt ({agent.BASE_URL})")


def post_chat(req_body):
    body = json.dumps(req_body).encode()
    req = urllib.request.Request(f"{agent.BASE_URL}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read())["choices"][0]["message"]
