"""Rendre la tour joignable : Tailscale (sur ce PC et sur la tour), Wake-on-LAN, réveil complet."""
import socket
import subprocess
from pathlib import Path

import tour
from tour import T, _print


def tailscale_local(log=_print):
    """Vérifie Tailscale sur CE PC et le relance s'il est arrêté."""
    exe = tour.TAILSCALE_LOCAL if Path(tour.TAILSCALE_LOCAL).exists() else "tailscale"
    try:
        st = subprocess.run([exe, "status"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=15)
    except Exception as e:
        log(f"   ⚠️ Tailscale introuvable sur ce PC ({e})")
        return False
    sortie = (st.stdout + st.stderr).lower()
    if st.returncode == 0 and "stopped" not in sortie and "logged out" not in sortie:
        return True
    if "logged out" in sortie or "log in" in sortie:
        log("   ⚠️ Tailscale de ce PC est déconnecté du compte : reconnecte-toi dans l'appli Tailscale")
        return False
    log("   ▶️ Tailscale arrêté sur ce PC : relance...")
    subprocess.run([exe, "up"], capture_output=True, text=True, timeout=60)
    tour.time.sleep(3)
    return True


def relancer_tailscale_tour(log=_print):
    """Tour allumée mais Tailscale coupé : relance par SSH via le réseau local."""
    if not tour.ssh_lan_ok():
        return False
    log("   ▶️ Tailscale coupé sur la tour : relance par le réseau local...")
    ts = T["tailscale_tour"]
    commande = ('powershell -NoProfile -Command "if ((Get-Service Tailscale).Status -ne \'Running\') '
                "{ Start-Service Tailscale; Start-Sleep 3 }; & '" + ts + "' up\"")
    try:
        tour._ssh_brut(T["ssh_lan"], commande)
    except subprocess.TimeoutExpired:
        pass
    for _ in range(10):
        if tour.ssh_ok():
            log("   ✅ Tailscale de la tour relancé")
            return True
        tour.time.sleep(3)
    log("   ❌ Tailscale de la tour ne revient pas (compte déconnecté ?)")
    return False


def wake_on_lan():
    mac = T["mac"].replace(":", "").replace("-", "")
    if len(mac) != 12:
        raise ValueError("Adresse MAC de la tour absente ou invalide dans config.json (rubrique « tour »)")
    paquet = bytes.fromhex("FF" * 6 + mac * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # 1) sur le réseau local (marche quand le ThinkPad est chez toi)
        for cible in {T["broadcast"], "255.255.255.255"}:
            for port in (9, 7):
                try:
                    s.sendto(paquet, (cible, port))
                except OSError:
                    pass
        # 2) vers ta box par Internet : elle relaie le réveil vers la tour (marche de partout)
        wi = T.get("wol_internet") or {}
        if wi.get("hote"):
            for port in wi.get("ports", [9]):
                try:
                    s.sendto(paquet, (wi["hote"], int(port)))
                except OSError:
                    pass


def _attendre_reveil(log):
    """Après le Wake-on-LAN : attend que la tour réponde (signal renvoyé de temps en temps). Vrai si elle répond."""
    debut = tour.time.time()
    while tour.time.time() - debut < T["attente_reveil_s"]:
        tour.time.sleep(5)
        if tour.time.time() - debut > 30:
            tour.wake_on_lan()  # on renvoie le signal de temps en temps
        if tour.lmstudio_ok() or tour.ssh_ok() or tour.ssh_lan_ok():
            log(f"   ✅ Tour réveillée en {tour.time.time() - debut:.0f} s")
            return True
    log(f"   ⚠️ La tour ne répond pas après {T['attente_reveil_s']} s "
        "(Wake-on-LAN pas actif, ou réseau injoignable)")
    return False


def reveiller(attendre=True, log=_print):
    """Rend le modèle de la tour joignable, en réparant ce qui est éteint :
    Tailscale de ce PC, tour en veille (Wake-on-LAN), Tailscale de la tour, serveur LM Studio.
    Renvoie True SEULEMENT si la tour dormait vraiment et que c'est nous qui l'avons
    réveillée (sinon on ne la rendormira jamais)."""
    tour.tailscale_local(log)
    if tour.lmstudio_ok():
        log("   La tour est allumée et son serveur LM Studio répond.")
        return False
    reveillee = False
    if not tour.ssh_ok() and not tour.ssh_lan_ok():
        log("   ⏰ Réveil de la tour (Wake-on-LAN)...")
        tour.wake_on_lan()
        if not attendre:
            return True
        if not _attendre_reveil(log):
            return False  # pas de preuve qu'on l'a réveillée : on ne la mettra pas en veille
        reveillee = True
    if not tour.ssh_ok() and tour.ssh_lan_ok():  # tour allumée mais Tailscale coupé
        tour.relancer_tailscale_tour(log)
    if not tour.lmstudio_ok():  # serveur LM Studio arrêté : on le démarre (sans toucher au reste)
        tour.demarrer_serveur(log)
    return reveillee
