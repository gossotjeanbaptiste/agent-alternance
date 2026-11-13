<#
Planifie une tâche de l'agent dans le Planificateur de tâches Windows.

Exemples :
  .\planifier.ps1 -Tache trier_telechargements -Heure 09:00          # tous les jours à 9h
  .\planifier.ps1 -Tache rapport_disque -Heure 18:30 -Jours Lundi,Vendredi
  .\planifier.ps1 -Tache trier_telechargements -AuDemarrage          # à chaque ouverture de session
  .\planifier.ps1 -Lister
  .\planifier.ps1 -Tache trier_telechargements -Supprimer
  .\planifier.ps1 -Tache trier_telechargements -Maintenant           # lance tout de suite (test)

La consigne est dans taches\<nom>.txt
#>
param(
    [string]$Tache,
    [string]$Heure,
    [string[]]$Jours,
    [switch]$AuDemarrage,
    [switch]$Lister,
    [switch]$Supprimer,
    [switch]$Maintenant
)

$ErrorActionPreference = "Stop"
$Dossier = $PSScriptRoot
$Prefixe = "lm_agent_"
$JoursMap = @{ Lundi="Monday"; Mardi="Tuesday"; Mercredi="Wednesday"; Jeudi="Thursday";
               Vendredi="Friday"; Samedi="Saturday"; Dimanche="Sunday" }

if ($Lister) {
    Get-ScheduledTask -TaskName "$Prefixe*" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $info = $_ | Get-ScheduledTaskInfo
            [pscustomobject]@{
                Tache = $_.TaskName.Substring($Prefixe.Length)
                Etat = $_.State
                Prochaine = $info.NextRunTime
                Derniere = $info.LastRunTime
            }
        } | Format-Table -AutoSize
    exit
}

if (-not $Tache) { Write-Host "Indique -Tache <nom> (voir le dossier taches\)"; exit 1 }
$Nom = "$Prefixe$Tache"

if ($Supprimer) {
    Unregister-ScheduledTask -TaskName $Nom -Confirm:$false
    Write-Host "Tâche '$Tache' supprimée."
    exit
}

if ($Maintenant) {
    Start-ScheduledTask -TaskName $Nom
    Write-Host "Tâche '$Tache' lancée. Suis-la dans logs\$(Get-Date -Format yyyy-MM-dd).log"
    exit
}

# Une routine Python dédiée (ex. alternance\alternance.py) ou une consigne taches\<nom>.txt
$Script = Get-ChildItem "$Dossier\*\$Tache.py", "$Dossier\$Tache.py" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Script) {
    $Arguments = "`"$($Script.FullName)`""
} elseif (Test-Path "$Dossier\taches\$Tache.txt") {
    $Arguments = "`"$Dossier\agent.py`" --tache $Tache"
} else {
    Write-Host "Introuvable : taches\$Tache.txt ou $Tache.py"; exit 1
}

# pythonw = pas de fenêtre noire qui s'ouvre
$Python = (Get-Command python).Source
$Pythonw = Join-Path (Split-Path $Python) "pythonw.exe"
if (Test-Path $Pythonw) { $Python = $Pythonw }

$Action = New-ScheduledTaskAction -Execute $Python `
    -Argument $Arguments -WorkingDirectory $Dossier

if ($AuDemarrage) {
    $Declencheur = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $Declencheur.Delay = "PT2M"   # attend 2 min après l'ouverture de session
    $Quand = "à chaque ouverture de session (+2 min)"
} elseif ($Heure) {
    if ($Jours) {
        $DaysEn = $Jours | ForEach-Object { $JoursMap[$_] }
        $Declencheur = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysEn -At $Heure
        $Quand = "chaque $($Jours -join ', ') à $Heure"
    } else {
        $Declencheur = New-ScheduledTaskTrigger -Daily -At $Heure
        $Quand = "tous les jours à $Heure"
    }
} else {
    Write-Host "Indique -Heure HH:MM ou -AuDemarrage"; exit 1
}

$Reglages = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $Nom -Action $Action -Trigger $Declencheur `
    -Settings $Reglages -Description "Agent IA local : $Tache" -Force | Out-Null

Write-Host "OK : '$Tache' planifiée $Quand."
Write-Host "Journal : $Dossier\logs\"
