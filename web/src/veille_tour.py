"""Quand l'utilisateur quitte LMAgent (icône près de l'horloge, bouton ⏻ de l'interface, Ctrl+C), la tour est remise
en veille (réglage « tour.veille_en_quittant »). Jamais pour une fermeture due à une mise à jour automatique
(LMAgent se relance tout de suite), ni pendant une routine (elle continue et a besoin de la tour), ni si la carte
graphique de la tour est occupée (quelqu'un s'en sert), ni si la tour est déjà injoignable (en veille, éteinte)."""
import json

import emplacements


def _journal(message):
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


def en_quittant(journal=_journal):
    """Met la tour en veille si tout le permet. Renvoie True si la mise en veille a été demandée."""
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
        if not (tour.ssh_ok() or tour.ssh_lan_ok()):
            return False                 # déjà en veille ou éteinte
        if tour.gpu_occupe(log=journal):
            journal("😴 Tour laissée allumée : sa carte graphique est occupée (quelqu'un s'en sert)")
            return False
        journal("😴 LMAgent quitté : mise en veille de la tour...")
        return bool(tour.veille(log=journal))
    except Exception as e:
        journal(f"⚠️ Mise en veille de la tour impossible : {e}")
        return False
