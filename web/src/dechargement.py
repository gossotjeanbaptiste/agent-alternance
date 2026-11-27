"""Déchargement du modèle des routines après une annulation (la routine arrêtée de force n'a pas pu le faire)."""


def decharger_modele():
    """Décharge le modèle des routines là où il est chargé (tour, ce PC) : une routine arrêtée de force n'a pas pu
    le faire. LM Studio reste ouvert ; seul le modèle réglé dans config.json est concerné."""
    import json
    import urllib.request
    import agent
    modele = agent.CONFIG.get("modele")
    bases = []
    for s in agent.CONFIG.get("serveurs") or [{"url": "local"}]:
        url = str(s.get("url") or "")
        bases += ["http://localhost:1234", "http://localhost:1235"] if url == "local" else [url.removesuffix("/v1")]
    dechargees = 0
    for base in dict.fromkeys(bases):
        try:
            with urllib.request.urlopen(base + "/api/v1/models", timeout=5) as r:
                infos = json.loads(r.read())
        except Exception:
            continue                      # serveur éteint ou injoignable : rien à décharger
        for m in infos.get("models", []):
            if m.get("key") != modele:
                continue
            for inst in m.get("loaded_instances") or []:
                req = urllib.request.Request(base + "/api/v1/models/unload", method="POST",
                                             data=json.dumps({"instance_id": inst["id"]}).encode(),
                                             headers={"Content-Type": "application/json"})
                try:
                    urllib.request.urlopen(req, timeout=60).close()
                    dechargees += 1
                except Exception:
                    pass
    try:
        dechargees += int(agent.npu.arreter())   # OpenVINO (NPU) lancé par la routine
    except Exception:
        pass
    return dechargees
