"""Pourquoi LM Studio ne démarre pas sur la tour (vérifications en lecture seule), et erreurs PowerShell lisibles."""
import html
import re

import tour
from tour import T


def erreur_powershell(r):
    """Message lisible d'un script PowerShell lancé par SSH : les erreurs, sans le bruit « #< CLIXML » (progression)."""
    if r is None:
        return "pas de réponse SSH (tour éteinte, en veille ou injoignable)"
    err = r.stderr or ""
    if "CLIXML" in err:
        lignes = re.findall(r'<S S="Error">(.*?)</S>', err, flags=re.S)
        err = " ".join(html.unescape(l).replace("_x000D__x000A_", " ") for l in lignes)
    err = " ".join(err.split())
    return err[:300] or f"le script s'est arrêté sans message (code {r.returncode})"


def diagnostic_lmstudio():
    """Pourquoi LM Studio ne répond pas sur la tour (vérifications en lecture seule) : phrase pour le journal."""
    lms = T["lms_tour"].replace("'", "''")
    r = tour.ps_distant(f"""
$ProgressPreference = 'SilentlyContinue'
'SESSION=' + [string](Get-CimInstance Win32_ComputerSystem).UserName
'LMS=' + [string](Test-Path -LiteralPath '{lms}')
'BIONIC=' + [string][bool](Get-Process Bionic -ErrorAction SilentlyContinue)
'TACHE=' + [string](Get-ScheduledTaskInfo -TaskName '{tour.TACHE_LMSTUDIO}' -ErrorAction SilentlyContinue).LastTaskResult
$installee = (Test-Path "$env:LOCALAPPDATA\\Programs\\LM Studio\\LM Studio.exe") -or [bool](Get-ChildItem `
  HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall, HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall `
  -ErrorAction SilentlyContinue | Get-ItemProperty | ? {{ $_.DisplayName -match 'LM Studio' }})
'APPLI=' + [string]$installee
'EN_ATTENTE=' + [string](Get-ChildItem "$env:LOCALAPPDATA\\lm-studio-updater\\pending" -Filter *.exe -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
""", timeout=30)
    return lire_diagnostic(r.stdout if r else None)


def lire_diagnostic(sortie):
    """Phrase de diagnostic d'après la sortie de diagnostic_lmstudio (testable sans la tour)."""
    if sortie is None:
        return "la tour ne répond plus en SSH (éteinte ou en veille ?)."
    v = dict(l.split("=", 1) for l in sortie.splitlines() if "=" in l)
    if not v.get("SESSION", "").strip():
        return ("aucune session Windows n'est ouverte sur la tour : ouvre ta session (elle peut rester verrouillée), "
                "puis réessaie.")
    if v.get("APPLI", "").strip() == "False":       # lms est là, mais plus l'appli (mise à jour interrompue)
        attente = v.get("EN_ATTENTE", "").strip()
        return ("l'appli LM Studio n'est plus installée sur la tour (mise à jour interrompue ?) : "
                + (f"lance l'installeur resté sur la tour ({attente}), puis réessaie." if attente
                   else "réinstalle LM Studio sur la tour, puis réessaie."))
    if v.get("LMS", "").strip() == "False":
        return (f"lms.exe introuvable sur la tour ({T['lms_tour']}) : corrige « Chemin de lms.exe sur la tour » "
                "dans Paramètres → Tour.")
    if v.get("BIONIC", "").strip() == "True":
        return (f"LM Studio est ouvert mais son serveur ne répond pas sur le port {T['port_serveur']} : "
                "démarre le serveur dans LM Studio (onglet Developer) ou vérifie le port dans Paramètres → Tour.")
    code = v.get("TACHE", "").strip()
    if code and code not in ("0", "267009"):        # 267009 = la tâche tourne encore
        return (f"la tâche qui lance LM Studio a échoué (code {code}) : ouvre LM Studio une fois à la main sur la "
                "tour (une fenêtre de mise à jour ou de connexion le bloque peut-être).")
    return ("LM Studio ne s'est pas lancé : ouvre-le une fois à la main sur la tour (une fenêtre de mise à jour ou "
            "de première ouverture le bloque peut-être), puis réessaie.")
