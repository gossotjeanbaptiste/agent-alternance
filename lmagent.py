"""Point d'entrée unique de LMAgent (c'est lui qui devient LMAgent.exe dans la version installée).

    lmagent.py                                  interface web (http://127.0.0.1:8765)
    lmagent.py --routine relances|recherche|tout [--essai] [--fois N]
    lmagent.py --postuler [--reponses]          assistant de candidature par formulaire
    lmagent.py --maj-tableau [--voir]           mise à jour interactive du tableau
    lmagent.py --agent [--task "…" | --tache nom]   agent en chat / tâche automatique

Depuis le code, les anciens scripts (web/app.py, alternance/relances.py…) marchent toujours.
"""
import subprocess
import sys
from pathlib import Path

ICI = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for p in (ICI / "alternance" / "src", ICI / "alternance", ICI / "web" / "src", ICI / "web", ICI):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

ROUTINES = ("relances", "recherche", "tout")
INTERACTIFS = ("--postuler", "--maj-tableau", "--agent")   # posent des questions au clavier


def sans_console():
    """Vrai dans l'exe installé (compilé sans fenêtre de console) quand rien ne récupère sa sortie."""
    return sys.stdout is None or sys.stderr is None


def sortie_vers_fichier(nom):
    """Sans console : print et erreurs vont dans logs/<nom>.txt. LMAGENT_SORTIE impose le fichier (routine lancée
    par l'interface, qui affiche ce fichier) et est transmise aux passages suivants d'une routine."""
    import os
    import emplacements
    chemin = Path(os.environ.get("LMAGENT_SORTIE") or emplacements.dossier("logs") / f"{nom}.txt")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    flux = open(chemin, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = flux
    os.environ["LMAGENT_SORTIE"] = str(chemin)
    return chemin


def ouvrir_console():
    """Sans console : en ouvre une pour les commandes interactives (--postuler, --maj-tableau, --agent)."""
    import ctypes
    k = ctypes.windll.kernel32
    k.AllocConsole()
    k.SetConsoleOutputCP(65001)
    k.SetConsoleCP(65001)
    sys.stdout = sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")


def preparer_sortie(args):
    """Choisit où va la sortie quand l'exe tourne sans console."""
    if not sans_console():
        return
    from datetime import datetime
    quand = f"{datetime.now():%Y%m%d_%H%M%S}"
    if any(o in args for o in INTERACTIFS):
        ouvrir_console()
    elif "--routine" in args:   # routine planifiée : visible dans l'historique de la page Routines
        sortie_vers_fichier(f"web_{quand}_{_valeur(args, '--routine', 'routine')}_planifiee")
    else:
        sortie_vers_fichier(f"interface_{quand}")
        import os
        os.environ.pop("LMAGENT_SORTIE", None)   # chaque routine lancée par l'interface reçoit son propre fichier


def commande_soi():
    """Commande qui relance LMAgent lui-même : l'exe (version installée) ou python lmagent.py (depuis le code)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve())]


def _valeur(args, option, defaut=None):
    if option in args:
        i = args.index(option)
        if i + 1 < len(args):
            return args[i + 1]
    return defaut


def routine(args):
    nom = _valeur(args, "--routine")
    if nom not in ROUTINES:
        sys.exit(f"Routine inconnue : {nom} (choisir parmi {', '.join(ROUTINES)})")
    essai = ["--essai"] if "--essai" in args else []
    try:
        fois = max(1, int(_valeur(args, "--fois", 1)))
    except ValueError:
        fois = 1
    if fois > 1:  # chaque passage dans un processus neuf (comme un lancement manuel)
        code = 0
        for i in range(fois):
            print(f"\n===== Passage {i + 1}/{fois} =====\n", flush=True)
            code = subprocess.call(commande_soi() + ["--routine", nom] + essai) or code
        return code
    sys.argv = ["alternance"] + essai
    import alternance
    alternance.main(nom)
    return 0


def script(module, args, options):
    sys.argv = [module] + [a for a in args if a in options]
    m = __import__(module)
    m.main()
    return 0


def agent(args):
    i = args.index("--agent")
    sys.argv = ["agent"] + args[i + 1:]
    import agent as module_agent
    module_agent.main()
    return 0


def interface():
    import mise_a_jour
    if mise_a_jour.au_demarrage():   # version installée : nouvelle version -> installation puis redémarrage
        return 0
    import app
    import icone_tache
    import routines
    mise_a_jour.surveiller(routines.en_cours, fermer=icone_tache.quitter)
    app.lancer_interface()
    return 0


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    preparer_sortie(args)
    if "--routine" in args:
        return routine(args)
    if "--postuler" in args:
        return script("postuler", args, {"--reponses"})
    if "--maj-tableau" in args:
        return script("maj_tableau", args, {"--voir"})
    if "--agent" in args:
        return agent(args)
    return interface()


if __name__ == "__main__":
    sys.exit(main())
