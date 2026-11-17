"""Appels de base à LM Studio sur ce PC : serveur joignable ?, commande lms.exe, appli ouverte ?"""
import subprocess
import urllib.request

import agent


def _reachable(url):
    try:
        urllib.request.urlopen(f"{url}/models", timeout=3)
        return True
    except Exception:
        return False


def _lms(*args, timeout=600):
    exe = str(agent.LMS) if agent.LMS.exists() else "lms"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _lmstudio_ouvert():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Bionic.exe", "/NH"],
                       capture_output=True, text=True, errors="replace")
    return "bionic.exe" in r.stdout.lower()
