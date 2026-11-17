"""Connexion SSH à la tour : par Tailscale (de partout), sinon par le réseau local ; scripts PowerShell à distance."""
import base64
import socket
import subprocess

import tour
from tour import T, _print


def _port_ouvert(cible, port=22):
    hote = cible.split("@")[-1]
    if not hote:
        return False
    try:
        with socket.create_connection((hote, port), timeout=4):
            return True
    except Exception:
        return False


def ssh_ok():
    """SSH de la tour joignable par Tailscale."""
    return _port_ouvert(T["ssh"])


def ssh_lan_ok():
    """SSH de la tour joignable par le réseau local (marche même si Tailscale est coupé)."""
    return bool(T.get("ssh_lan")) and _port_ouvert(T["ssh_lan"])


def _cible_ssh():
    """Le chemin SSH qui marche : Tailscale d'abord, réseau local sinon."""
    if tour.ssh_ok():
        return T["ssh"]
    if tour.ssh_lan_ok():
        return T["ssh_lan"]
    return None


def _ssh_brut(cible, commande, timeout=90):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
         cible, commande],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def ps_distant(script, timeout=90):
    """Exécute un script PowerShell sur la tour (par le chemin SSH qui marche)."""
    cible = tour._cible_ssh()
    if not cible:
        return None
    code = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        return tour._ssh_brut(cible, f"powershell -NoProfile -EncodedCommand {code}", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def ssh(commande_ps, timeout=20):
    """Lance une commande PowerShell sur la tour via SSH (clé, sans mot de passe)."""
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
         tour._cible_ssh() or T["ssh"], f'powershell -NoProfile -Command "{commande_ps}"'],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _ssh_action(commande_ps, quoi, log=_print):
    try:
        r = tour.ssh(commande_ps)
    except subprocess.TimeoutExpired:
        log(f"   ✅ {quoi} (la connexion s'est coupée, c'est normal)")
        return True
    err = (r.stderr or "").lower()
    if r.returncode == 0:
        log(f"   ✅ {quoi}")
        return True
    if r.returncode == 255 and ("closed" in err or "reset" in err):  # la tour s'endort / s'éteint
        log(f"   ✅ {quoi} (la connexion s'est coupée, c'est normal)")
        return True
    if "permission denied" in err or "publickey" in err:
        log("   ❌ SSH refuse la connexion : la clé du ThinkPad n'est pas installée sur la tour (voir le guide)")
    elif "timed out" in err or "could not resolve" in err or "refused" in err:
        log("   ❌ SSH injoignable : la tour est éteinte, ou le serveur OpenSSH n'y est pas installé (voir le guide)")
    else:
        log(f"   ❌ Échec ({quoi}) : {(r.stderr or r.stdout).strip()[:300]}")
    return False
