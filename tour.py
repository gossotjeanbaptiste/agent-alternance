"""
Pilotage de la tour à distance (depuis le ThinkPad).

    python tour.py etat          -> la tour est-elle allumée ? LM Studio ? SSH ?
    python tour.py reveiller     -> Wake-on-LAN si elle dort + démarre le serveur LM Studio si besoin
    python tour.py serveur       -> démarre le serveur LM Studio de la tour (l'ouvre si besoin)
    python tour.py fermer-lmstudio -> ferme LM Studio sur la tour
    python tour.py tailscale     -> relance Tailscale sur ce PC, et sur la tour si besoin
    python tour.py veille        -> met la tour en veille
    python tour.py eteindre      -> éteint la tour (60 s de délai, annulable)
    python tour.py redemarrer    -> redémarre la tour
    python tour.py annuler       -> annule un arrêt / redémarrage en cours
    ajoute --oui pour ne pas avoir de confirmation, --maintenant pour éteindre sans délai

Réglages : rubrique "tour" de config.json.
- Le réveil (Wake-on-LAN) est envoyé sur le réseau local ET à la box par Internet
  (rubrique "wol_internet") : la box le relaie vers la tour, donc ça marche aussi hors de chez toi.
- Veille / arrêt / démarrage de LM Studio passent par SSH via Tailscale (de partout), ou par le
  réseau local ("ssh_lan") si Tailscale est coupé sur la tour.
"""
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
_cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
T = {
    "mac": "",
    "broadcast": "192.168.1.255",
    "ssh": "utilisateur@nom-de-la-tour",
    "url_lmstudio": "http://nom-de-la-tour:1236/v1",
    "attente_reveil_s": 150,
    "veille_apres": False,
    "port_serveur": 1235,   # port du serveur LM Studio SUR la tour (le relais 1236 y renvoie)
    "lms_tour": r"C:\Users\utilisateur\.lmstudio\bin\lms.exe",  # chemin de lms.exe sur la tour
    "ssh_lan": "",          # ex. "utilisateur@192.168.1.XX" : SSH par le réseau local, si Tailscale est coupé
    "tailscale_tour": r"C:\Program Files\Tailscale\tailscale.exe",
    "fermer_lmstudio_apres": True,  # ferme LM Studio à la fin, seulement si c'est le script qui l'a ouvert
    "verifier_gpu": True,           # ne pas utiliser la tour si sa carte graphique est déjà occupée (jeu…)
    "vram_libre_min_mo": 7000,      # mémoire libre nécessaire pour charger le modèle (~6,1 Go + contexte)
    "gpu_utilisation_max": 40,      # au-delà (en %), la carte est considérée occupée
    **_cfg.get("tour", {}),
}


def _print(msg):
    print(msg, flush=True)


LMSTUDIO_OUVERT_PAR_SCRIPT = False  # True si LM Studio était fermé sur la tour et que le script l'a ouvert
TACHE_LMSTUDIO = "lm_agent_lmstudio"


# --- État ----------------------------------------------------------------------
def lmstudio_ok(timeout=3):
    try:
        urllib.request.urlopen(f"{T['url_lmstudio']}/models", timeout=timeout)
        return True
    except Exception:
        return False


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
    if ssh_ok():
        return T["ssh"]
    if ssh_lan_ok():
        return T["ssh_lan"]
    return None


def _ssh_brut(cible, commande, timeout=90):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
         cible, commande],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def ps_distant(script, timeout=90):
    """Exécute un script PowerShell sur la tour (par le chemin SSH qui marche)."""
    import base64
    cible = _cible_ssh()
    if not cible:
        return None
    code = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        return _ssh_brut(cible, f"powershell -NoProfile -EncodedCommand {code}", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def lmstudio_ouvert_tour():
    """L'appli LM Studio tourne-t-elle sur la tour ?"""
    r = ps_distant("if (Get-Process Bionic -ErrorAction SilentlyContinue) { 'OUI' } else { 'NON' }", timeout=30)
    return bool(r) and "OUI" in r.stdout


def ouvrir_lmstudio_tour(log=_print):
    """Ouvre LM Studio (serveur démarré) DANS ta session Windows de la tour, même verrouillée.
    Passe par une tâche planifiée : un programme lancé directement par SSH serait tué à la
    déconnexion. La tâche est créée automatiquement la première fois."""
    lms = T["lms_tour"].replace("'", "''")
    script = f"""
$t = Get-ScheduledTask -TaskName '{TACHE_LMSTUDIO}' -ErrorAction SilentlyContinue
if (-not $t) {{
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -NoProfile -Command & '{lms}' server start --port {T['port_serveur']}"
  $p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
  $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
  Register-ScheduledTask -TaskName '{TACHE_LMSTUDIO}' -Action $a -Principal $p -Settings $s -Description 'lm_agent : ouvre LM Studio et son serveur' -Force | Out-Null
}}
Start-ScheduledTask -TaskName '{TACHE_LMSTUDIO}'
"""
    log("   ▶️ Ouverture de LM Studio sur la tour...")
    r = ps_distant(script)
    for _ in range(30):
        if lmstudio_ok():
            log("   ✅ LM Studio ouvert sur la tour, serveur prêt")
            return True
        time.sleep(3)
    log(f"   ❌ LM Studio ne répond pas sur la tour ({(r.stderr.strip()[:200] if r else 'pas de réponse SSH')})."
        " Ta session Windows est-elle ouverte sur la tour ?")
    return False


def fermer_lmstudio_si_ouvert(log=_print):
    """Ferme LM Studio sur la tour, SEULEMENT si c'est le script qui l'a ouvert."""
    global LMSTUDIO_OUVERT_PAR_SCRIPT
    if not LMSTUDIO_OUVERT_PAR_SCRIPT or not T.get("fermer_lmstudio_apres", True):
        return
    LMSTUDIO_OUVERT_PAR_SCRIPT = False
    lms = T["lms_tour"].replace("'", "''")
    ps_distant(f"& '{lms}' server stop | Out-Null; Start-Sleep 2; Stop-Process -Name Bionic -ErrorAction SilentlyContinue")
    log("   🧹 LM Studio fermé sur la tour (il avait été ouvert par le script)")


TAILSCALE_LOCAL = T.get("tailscale_local") or r"C:\Program Files\Tailscale\tailscale.exe"


def tailscale_local(log=_print):
    """Vérifie Tailscale sur CE PC et le relance s'il est arrêté."""
    exe = TAILSCALE_LOCAL if Path(TAILSCALE_LOCAL).exists() else "tailscale"
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
    time.sleep(3)
    return True


def relancer_tailscale_tour(log=_print):
    """Tour allumée mais Tailscale coupé : relance par SSH via le réseau local."""
    if not ssh_lan_ok():
        return False
    log("   ▶️ Tailscale coupé sur la tour : relance par le réseau local...")
    ts = T["tailscale_tour"]
    commande = ('powershell -NoProfile -Command "if ((Get-Service Tailscale).Status -ne \'Running\') '
                "{ Start-Service Tailscale; Start-Sleep 3 }; & '" + ts + "' up\"")
    try:
        _ssh_brut(T["ssh_lan"], commande)
    except subprocess.TimeoutExpired:
        pass
    for _ in range(10):
        if ssh_ok():
            log("   ✅ Tailscale de la tour relancé")
            return True
        time.sleep(3)
    log("   ❌ Tailscale de la tour ne revient pas (compte déconnecté ?)")
    return False


# --- Réveil ----------------------------------------------------------------------
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


def modele_charge():
    """Notre modèle est-il déjà chargé sur la tour ? (sa mémoire est alors déjà réservée)"""
    try:
        import json
        base = T["url_lmstudio"].rstrip("/")
        base = base[:-3] if base.endswith("/v1") else base
        with urllib.request.urlopen(f"{base}/api/v1/models", timeout=5) as r:
            infos = json.loads(r.read())
        modele = _cfg.get("modele", "")
        return any(m.get("key") == modele and m.get("loaded_instances") for m in infos.get("models", []))
    except Exception:
        return False


def lire_gpu():
    """Mémoire et charge de la carte graphique de la tour (nvidia-smi par SSH, simple lecture).
    Renvoie {"libre_mo", "total_mo", "utilisation"} ou None si impossible à lire."""
    cible = _cible_ssh()
    if not cible:
        return None
    try:
        r = _ssh_brut(cible, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu "
                             "--format=csv,noheader,nounits", timeout=20)
    except subprocess.TimeoutExpired:
        return None
    return analyser_nvidia_smi(r.stdout if r and r.returncode == 0 else "")


def analyser_nvidia_smi(sortie):
    """« 5120, 8188, 87 » -> {"libre_mo": 3068, "total_mo": 8188, "utilisation": 87}"""
    try:
        utilise, total, charge = [int(float(x)) for x in sortie.strip().splitlines()[0].split(",")[:3]]
        return {"libre_mo": total - utilise, "total_mo": total, "utilisation": charge}
    except Exception:
        return None


def gpu_occupe(log=_print):
    """Vrai si la carte graphique de la tour sert déjà à autre chose (un jeu, par exemple) :
    pas assez de mémoire libre pour le modèle, ou carte déjà très sollicitée.
    Dans ce cas on laisse la tour tranquille et le travail se fait sur ce PC."""
    if not T.get("verifier_gpu", True) or modele_charge():
        return False  # vérification désactivée, ou modèle déjà en place : rien de plus à réserver
    g = lire_gpu()
    if g is None:
        log("   ℹ️ Impossible de lire l'état de la carte graphique de la tour : on l'utilise quand même")
        return False
    raisons = []
    if g["libre_mo"] < T["vram_libre_min_mo"]:
        raisons.append(f"{g['libre_mo']} Mo libres sur {g['total_mo']} (il en faut {T['vram_libre_min_mo']})")
    if g["utilisation"] > T["gpu_utilisation_max"]:
        raisons.append(f"utilisée à {g['utilisation']} %")
    if raisons:
        log(f"   🎮 Carte graphique de la tour occupée ({', '.join(raisons)}) : un jeu tourne sans doute,"
            " on n'y touche pas et le travail se fait sur ce PC")
        return True
    return False


def demarrer_serveur(log=_print):
    """Démarre le serveur LM Studio de la tour par SSH (si l'appli est fermée ou le serveur arrêté)."""
    global LMSTUDIO_OUVERT_PAR_SCRIPT
    cible = _cible_ssh()
    if not cible:
        log("   ❌ Impossible de joindre la tour en SSH pour démarrer LM Studio")
        return False
    if not lmstudio_ouvert_tour():  # appli fermée : on l'ouvre dans ta session
        ok = ouvrir_lmstudio_tour(log)
        LMSTUDIO_OUVERT_PAR_SCRIPT = ok
        return ok
    log("   ▶️ Démarrage du serveur LM Studio de la tour...")
    try:
        r = _ssh_brut(cible, f"{T['lms_tour']} server start --port {T['port_serveur']}")
    except subprocess.TimeoutExpired:
        r = None
    for _ in range(12):
        if lmstudio_ok():
            log("   ✅ Serveur LM Studio de la tour démarré")
            return True
        time.sleep(3)
    detail = (r.stderr or r.stdout).strip()[:200] if r else "délai dépassé"
    log(f"   ❌ Impossible de démarrer le serveur LM Studio de la tour ({detail})")
    return False


def reveiller(attendre=True, log=_print):
    """Rend le modèle de la tour joignable, en réparant ce qui est éteint :
    Tailscale de ce PC, tour en veille (Wake-on-LAN), Tailscale de la tour, serveur LM Studio.
    Renvoie True SEULEMENT si la tour dormait vraiment et que c'est nous qui l'avons
    réveillée (sinon on ne la rendormira jamais)."""
    tailscale_local(log)
    if lmstudio_ok():
        log("   La tour est allumée et son serveur LM Studio répond.")
        return False
    reveillee = False
    if not ssh_ok() and not ssh_lan_ok():
        log("   ⏰ Réveil de la tour (Wake-on-LAN)...")
        wake_on_lan()
        if not attendre:
            return True
        debut = time.time()
        while time.time() - debut < T["attente_reveil_s"]:
            time.sleep(5)
            if time.time() - debut > 30:
                wake_on_lan()  # on renvoie le signal de temps en temps
            if lmstudio_ok() or ssh_ok() or ssh_lan_ok():
                reveillee = True
                log(f"   ✅ Tour réveillée en {time.time() - debut:.0f} s")
                break
        else:
            log(f"   ⚠️ La tour ne répond pas après {T['attente_reveil_s']} s "
                "(Wake-on-LAN pas actif, ou réseau injoignable)")
            return False  # pas de preuve qu'on l'a réveillée : on ne la mettra pas en veille
    if not ssh_ok() and ssh_lan_ok():  # tour allumée mais Tailscale coupé
        relancer_tailscale_tour(log)
    if not lmstudio_ok():  # serveur LM Studio arrêté : on le démarre (sans toucher au reste)
        demarrer_serveur(log)
    return reveillee


# --- Commandes à distance (SSH) ------------------------------------------------------
def ssh(commande_ps, timeout=20):
    """Lance une commande PowerShell sur la tour via SSH (clé, sans mot de passe)."""
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
         _cible_ssh() or T["ssh"], f'powershell -NoProfile -Command "{commande_ps}"'],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _ssh_action(commande_ps, quoi, log=_print):
    try:
        r = ssh(commande_ps)
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


def veille(log=_print):
    return _ssh_action(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
        "Tour mise en veille", log)


def eteindre(delai=60, log=_print):
    return _ssh_action(f"shutdown /s /t {delai} /c 'Arrêt demandé à distance (lm_agent)'",
                       f"Arrêt de la tour dans {delai} s (annulable : python tour.py annuler)", log)


def redemarrer(delai=60, log=_print):
    return _ssh_action(f"shutdown /r /t {delai} /c 'Redémarrage demandé à distance (lm_agent)'",
                       f"Redémarrage de la tour dans {delai} s (annulable : python tour.py annuler)", log)


def annuler(log=_print):
    return _ssh_action("shutdown /a", "Arrêt / redémarrage annulé", log)


# --- Ligne de commande ----------------------------------------------------------------
def _confirmer(question, args):
    if "--oui" in args:
        return True
    return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y")


def main(args):
    if not args or args[0] in ("-h", "--help", "aide"):
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "etat":
        def ok(b):
            return "✅ joignable" if b else "❌ injoignable"
        print(f"LM Studio de la tour         : {ok(lmstudio_ok())}")
        print(f"SSH de la tour (Tailscale)   : {ok(ssh_ok())}")
        if T.get("ssh_lan"):
            print(f"SSH de la tour (réseau local): {ok(ssh_lan_ok())}")
    elif cmd == "reveiller":
        reveiller()
    elif cmd == "serveur":
        demarrer_serveur()
    elif cmd == "fermer-lmstudio":
        global LMSTUDIO_OUVERT_PAR_SCRIPT
        LMSTUDIO_OUVERT_PAR_SCRIPT = True
        fermer_lmstudio_si_ouvert()
    elif cmd == "tailscale":
        tailscale_local()
        if not ssh_ok():
            relancer_tailscale_tour()
    elif cmd == "veille":
        if _confirmer("Mettre la tour en veille ?", args):
            veille()
    elif cmd == "eteindre":
        if _confirmer("Éteindre la tour ?", args):
            eteindre(0 if "--maintenant" in args else 60)
    elif cmd == "redemarrer":
        if _confirmer("Redémarrer la tour ?", args):
            redemarrer(0 if "--maintenant" in args else 60)
    elif cmd == "annuler":
        annuler()
    else:
        print(f"Commande inconnue : {cmd}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
