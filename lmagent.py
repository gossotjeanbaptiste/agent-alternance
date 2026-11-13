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
    import routines
    mise_a_jour.surveiller(routines.en_cours)
    app.lancer_interface()
    return 0


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
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
