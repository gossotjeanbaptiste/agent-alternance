"""Quand l'utilisateur quitte LMAgent (icône près de l'horloge, bouton ⏻ de l'interface, Ctrl+C), LM Studio est fermé
sur la tour puis la tour est remise en veille (réglage « tour.veille_en_quittant »). Jamais pour une fermeture due à
une mise à jour automatique (LMAgent se relance tout de suite), ni pendant une routine (elle continue et a besoin de
la tour), ni si la carte graphique de la tour est occupée (quelqu'un s'en sert), ni si la tour est déjà injoignable.
Chaque étape est notée dans ARRET : la page de fermeture l'affiche en direct (/api/arret)."""
import json

import emplacements

ARRET = {"lignes": [], "fini": False}     # journal de la fermeture, lu par la page pendant qu'elle se fait


def _journal(message):
    ARRET["lignes"].append(message.strip())
    print(message)
    try:
        import agent
        agent.log(message)
    except Exception:
        pass


def active():
    """Réglage lu dans config.json au moment de quitter (il a pu changer depuis le lancement)."""
    try:
        c = json.loads(emplacements.config_agent().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        c = {}
    import agent
    return agent.utiliser_tour(c) and bool((c.get("tour") or {}).get("veille_en_quittant", True))


def _fermer_lmstudio(tour, journal):
    """LM Studio fermé sur la tour avant sa mise en veille (modèle déchargé, carte graphique libérée)."""
    if not tour.lmstudio_ouvert_tour():
        return
    journal("🧹 Fermeture de LM Studio sur la tour...")
    lms = str(tour.T.get("lms_tour") or "lms").replace("'", "''")
    tour.ps_distant(f"& '{lms}' server stop | Out-Null; Start-Sleep 2; "
                    "Stop-Process -Name Bionic -ErrorAction SilentlyContinue", timeout=60)
    journal("   ✅ LM Studio fermé sur la tour")


def en_quittant(journal=_journal):
    """Ferme LM Studio sur la tour et la met en veille si tout le permet. Renvoie True si la veille a été demandée."""
    try:
        if not active():
            return False
        import tour                      # absent de la branche local-simple
    except ImportError:
        return False
    try:
        import routines
        if routines.en_cours():
            journal("😴 Tour laissée allumée : une routine continue et s'en sert")
            return False
        journal("🔎 La tour est-elle allumée ?")
        if not (tour.ssh_ok() or tour.ssh_lan_ok()):
            journal("   Tour déjà en veille ou éteinte : rien à faire")
            return False
        if tour.gpu_occupe(log=journal):
            journal("😴 Tour laissée allumée : sa carte graphique est occupée (quelqu'un s'en sert)")
            return False
        _fermer_lmstudio(tour, journal)
        journal("😴 Mise en veille de la tour...")
        return bool(tour.veille(log=journal))
    except Exception as e:
        journal(f"⚠️ Mise en veille de la tour impossible : {e}")
        return False
