"""LM Studio sur la tour : serveur joignable ?, appli ouverte ?, ouverture dans ta session, démarrage du serveur,
fermeture (seulement si c'est le script qui l'a ouvert), modèle déjà chargé ?"""
import json
import subprocess
import urllib.request

import tour
from tour import T, _print


def lmstudio_ok(timeout=3):
    try:
        urllib.request.urlopen(f"{T['url_lmstudio']}/models", timeout=timeout)
        return True
    except Exception:
        return False


def lmstudio_ouvert_tour():
    """L'appli LM Studio tourne-t-elle sur la tour ?"""
    r = tour.ps_distant("if (Get-Process Bionic -ErrorAction SilentlyContinue) { 'OUI' } else { 'NON' }", timeout=30)
    return bool(r) and "OUI" in r.stdout


def ouvrir_lmstudio_tour(log=_print):
    """Ouvre LM Studio (serveur démarré) DANS ta session Windows de la tour, même verrouillée.
    Passe par une tâche planifiée : un programme lancé directement par SSH serait tué à la
    déconnexion. La tâche est créée automatiquement la première fois."""
    lms = T["lms_tour"].replace("'", "''")
    nom = tour.TACHE_LMSTUDIO
    # tâche recréée à chaque fois (-Force) : le chemin de lms et le port restent ceux des réglages actuels
    script = f"""
$ProgressPreference = 'SilentlyContinue'
$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -NoProfile -Command & '{lms}' server start --port {T['port_serveur']}"
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName '{nom}' -Action $a -Principal $p -Settings $s -Description 'lm_agent : ouvre LM Studio et son serveur' -Force | Out-Null
Start-ScheduledTask -TaskName '{nom}'
'TACHE_LANCEE'
"""
    log("   ▶️ Ouverture de LM Studio sur la tour...")
    r = tour.ps_distant(script)
    if r is None or "TACHE_LANCEE" not in (r.stdout or ""):
        log(f"   ❌ Impossible de lancer LM Studio sur la tour : {tour.erreur_powershell(r)}")
        return False
    for _ in range(30):
        if tour.lmstudio_ok():
            log("   ✅ LM Studio ouvert sur la tour, serveur prêt")
            return True
        tour.time.sleep(3)
    log(f"   ❌ LM Studio ne répond pas sur la tour : {tour.diagnostic_lmstudio()}")
    return False


def fermer_lmstudio_si_ouvert(log=_print):
    """Ferme LM Studio sur la tour, SEULEMENT si c'est le script qui l'a ouvert."""
    if not tour.LMSTUDIO_OUVERT_PAR_SCRIPT or not T.get("fermer_lmstudio_apres", True):
        return
    tour.LMSTUDIO_OUVERT_PAR_SCRIPT = False
    lms = T["lms_tour"].replace("'", "''")
    tour.ps_distant(f"& '{lms}' server stop | Out-Null; Start-Sleep 2; Stop-Process -Name Bionic -ErrorAction SilentlyContinue")
    log("   🧹 LM Studio fermé sur la tour (il avait été ouvert par le script)")


def demarrer_serveur(log=_print):
    """Démarre le serveur LM Studio de la tour par SSH (si l'appli est fermée ou le serveur arrêté)."""
    cible = tour._cible_ssh()
    if not cible:
        log("   ❌ Impossible de joindre la tour en SSH pour démarrer LM Studio")
        return False
    if not tour.lmstudio_ouvert_tour():  # appli fermée : on l'ouvre dans ta session
        ok = tour.ouvrir_lmstudio_tour(log)
        tour.LMSTUDIO_OUVERT_PAR_SCRIPT = ok
        return ok
    log("   ▶️ Démarrage du serveur LM Studio de la tour...")
    try:
        r = tour._ssh_brut(cible, f"{T['lms_tour']} server start --port {T['port_serveur']}")
    except subprocess.TimeoutExpired:
        r = None
    for _ in range(12):
        if tour.lmstudio_ok():
            log("   ✅ Serveur LM Studio de la tour démarré")
            return True
        tour.time.sleep(3)
    detail = tour.erreur_powershell(r) if r else "délai dépassé"
    log(f"   ❌ Impossible de démarrer le serveur LM Studio de la tour ({detail}) : {tour.diagnostic_lmstudio()}")
    return False


def modele_charge():
    """Notre modèle est-il déjà chargé sur la tour ? (sa mémoire est alors déjà réservée)"""
    try:
        base = T["url_lmstudio"].rstrip("/")
        base = base[:-3] if base.endswith("/v1") else base
        with urllib.request.urlopen(f"{base}/api/v1/models", timeout=5) as r:
            infos = json.loads(r.read())
        modele = tour._cfg.get("modele", "")
        return any(m.get("key") == modele and m.get("loaded_instances") for m in infos.get("models", []))
    except Exception:
        return False
