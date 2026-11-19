"""Choix du serveur qui fait tourner le modèle (la tour d'abord, ce PC en dernier recours), chargement du modèle,
envoi des requêtes (avec bascule sur le serveur suivant si celui-ci lâche)."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import agent


ESSAIS_CHARGEMENT = 3      # LM Studio tout juste ouvert répond avant d'être prêt à charger un modèle
ATTENTE_CHARGEMENT_S = 5


def _charger_une_fois(nom, base):
    """Instance du modèle sur le serveur distant : celle déjà chargée, sinon chargée maintenant."""
    c = agent.CONFIG
    infos = agent._api(base, "GET", "/api/v1/models", timeout=15)
    m = next((x for x in infos.get("models", []) if x.get("key") == c["modele"]), {})
    instances = m.get("loaded_instances") or []
    if instances:
        return instances[0]["id"]
    agent.say(f"   Chargement de {c['modele']} sur {nom}...")
    t = time.time()
    r = agent._api(base, "POST", "/api/v1/models/load",
                   {"model": c["modele"], "context_length": int(c["contexte"])})
    agent.say(f"   Modèle chargé sur {nom} en {time.time() - t:.0f} s")
    return r.get("instance_id") or r.get("id") or c["modele"]


def _charger_distant(nom, url):
    """Charge le modèle sur un PC distant (la tour) via l'API REST de LM Studio. Une connexion coupée (LM Studio
    qui vient de s'ouvrir et n'est pas encore prêt) est réessayée après quelques secondes."""
    base = url[:-3] if url.endswith("/v1") else url
    for essai in range(1, ESSAIS_CHARGEMENT + 1):
        try:
            inst = _charger_une_fois(nom, base)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if essai < ESSAIS_CHARGEMENT:
                agent.say(f"   ⏳ {nom} pas encore prêt ({e}) : nouvel essai dans {ATTENTE_CHARGEMENT_S} s")
                time.sleep(ATTENTE_CHARGEMENT_S)
                continue
            agent.say(f"   ⚠️ Chargement explicite impossible sur {nom} ({e}) : chargement automatique à la première demande")
            return
        except Exception as e:
            agent.say(f"   ⚠️ Chargement explicite impossible sur {nom} ({e}) : chargement automatique à la première demande")
            return
        if agent.CONFIG.get("decharger_a_la_fin", True):
            agent.A_DECHARGER.append(("distant", nom, base, inst))
        return


def _lmstudio_demarre():
    """URL du serveur LM Studio de CE PC (appli ouverte en arrière-plan et serveur démarré si besoin), ou None."""
    candidates = [f"http://localhost:{p}/v1" for p in (1234, 1235)]
    url = next((u for u in candidates if agent._reachable(u)), None)
    if url:
        return url
    if not agent.LMS.exists():
        agent.say("   LM Studio absent de ce PC : on passe au suivant")
        return None
    if not agent._lmstudio_local_ouvert() and agent.CONFIG.get("fermer_lmstudio_apres", True):
        agent.LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT = True  # « lms server start » va l'ouvrir : on le refermera
    agent.say("Démarrage du serveur LM Studio local...")
    agent._lms("server", "start")
    time.sleep(3)
    return next((u for u in candidates if agent._reachable(u)), None)


def a_decharger_local():
    """Modèle chargé dans LM Studio de ce PC, tel que liberation.py le décharge à la fin."""
    return ("local", "ce PC", None, agent.CONFIG["modele"])


def _serveurs_a_essayer():
    """Serveurs dans l'ordre : LMSTUDIO_URL, ceux de config.json (sans la tour si elle n'est pas utilisée), ce PC
    en dernier recours. « ce PC » est remplacé par ses niveaux (carte dédiée, NPU, carte du processeur, processeur),
    cherchés seulement quand on en arrive là."""
    liste = list(agent.CONFIG.get("serveurs") or [])
    if not agent.utiliser_tour():  # pas de deuxième PC : uniquement ce PC (aucun réveil, aucune attente)
        liste = [s for s in liste if s.get("url") == "local"]
    if os.environ.get("LMSTUDIO_URL"):
        liste.insert(0, {"nom": "LMSTUDIO_URL", "url": os.environ["LMSTUDIO_URL"]})
    if not any(s.get("url") == "local" for s in liste):
        liste.append({"nom": "ce PC", "url": "local"})
    for s in liste:
        if s.get("url") == "local":
            yield from ({"nom": nom, "url": "local", "niveau": n} for n, nom in agent.niveaux_locaux())
        else:
            yield s


def _serveur_distant(s):
    """URL du serveur distant s (la tour), réveillée si besoin ; None s'il est injoignable ou occupé."""
    url = s["url"].rstrip("/")
    if s.get("reveil"):
        try:
            import tour
            # Tour allumée et carte graphique déjà prise (jeu…) : on n'y touche pas du tout.
            allumee = agent._reachable(url) or tour.ssh_ok() or tour.ssh_lan_ok()
            if allumee and tour.gpu_occupe(log=agent.say):
                return None
        except Exception as e:
            agent.say(f"   ⚠️ Vérification de la tour impossible : {e}")
        if not agent._reachable(url):
            try:
                import tour
                agent.TOUR_REVEILLEE = tour.reveiller(log=agent.say) or agent.TOUR_REVEILLEE
            except Exception as e:
                agent.say(f"   ⚠️ Réveil de la tour impossible : {e}")
    if not agent._reachable(url):
        agent.say(f"   {s['nom']} injoignable ({s['url']}), on passe au suivant")
        return None
    agent._charger_distant(s["nom"], url)
    return url


def ensure_server(sauf=()):
    """Choisit le serveur : LMSTUDIO_URL s'il est défini, sinon la liste « serveurs » de config.json
    dans l'ordre (la tour d'abord), et ce PC en dernier recours."""
    for s in _serveurs_a_essayer():
        if s["nom"] in sauf:
            continue
        if s["url"] == "local":
            url = agent.demarrer_local(s["niveau"])
        else:
            agent.MOTEUR = "lmstudio"
            url = _serveur_distant(s)
        if url:
            agent.BASE_URL, agent.SERVEUR = url, s["nom"]
            agent.say(f"🧠 Modèle utilisé : {agent.SERVEUR} ({agent.BASE_URL})")
            return
    agent.say("❌ Aucun serveur LM Studio disponible (ni la tour, ni ce PC).")
    sys.exit(1)


def post_chat(req_body):
    """Envoie une requête au modèle. Si le serveur lâche en cours de route (tour éteinte,
    connexion coupée), bascule une fois sur le serveur suivant et recommence."""
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
            agent.say(f"⚠️ {agent.SERVEUR} ne répond plus ({e}) : bascule sur le serveur suivant")
            if agent.MOTEUR == "openvino":
                agent.npu.arreter()
            agent.ECARTES.append(agent.SERVEUR)       # les serveurs déjà lâchés ne sont pas réessayés
            agent.ensure_server(sauf=tuple(agent.ECARTES))
