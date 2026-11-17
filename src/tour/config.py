"""Réglages de la tour : rubrique « tour » de config.json, complétée par des valeurs par défaut.
Se charge même sans config.json (installation neuve : la tour n'est pas encore utilisée)."""
import json

import emplacements

try:
    _cfg = json.loads(emplacements.config_agent().read_text(encoding="utf-8"))
except (FileNotFoundError, ValueError):
    _cfg = {}   # installation neuve : pas encore de config (la tour n'est pas utilisée)

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
