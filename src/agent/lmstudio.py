"""Appels de base à LM Studio : serveur joignable ?, API REST, commande lms.exe, appli ouverte sur ce PC ?"""
import json
import subprocess
import urllib.request

import agent


def _reachable(url):
    try:
        urllib.request.urlopen(f"{url}/models", timeout=3)
        return True
    except Exception:
        return False


def _lms(*args, timeout=300):
    exe = str(agent.LMS) if agent.LMS.exists() else "lms"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _api(base, methode, chemin, corps=None, timeout=180):
    req = urllib.request.Request(base + chemin, method=methode,
                                 data=None if corps is None else json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = r.read()
    return json.loads(txt) if txt else {}


def _lmstudio_local_ouvert():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Bionic.exe", "/NH"],
                       capture_output=True, text=True, errors="replace")
    return "bionic.exe" in r.stdout.lower()
