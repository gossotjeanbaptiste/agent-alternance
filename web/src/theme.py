"""Thème de l'interface (réglage « interface.theme ») : clair, sombre, ou celui du système (par défaut).
La page reçoit data-theme="clair" / "sombre" sur <html> ; sans attribut, style.css suit le thème de Windows."""

CHOIX = {"clair": "clair", "sombre": "sombre"}


def attribut():
    """Valeur de data-theme pour <html> (« clair », « sombre »), ou "" pour suivre le thème du système."""
    try:
        import reglages
        choix = str(reglages.valeur("interface.theme") or "").lower()
    except Exception:            # pas encore de configuration (premier lancement) : thème du système
        return ""
    return next((v for k, v in CHOIX.items() if choix.startswith(k)), "")
