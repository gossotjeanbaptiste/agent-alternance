"""Point d'entrée unique de LMAgent (c'est lui qui devient LMAgent.exe dans la version installée).

    lmagent.py                                  interface web (http://127.0.0.1:8765)
    lmagent.py --routine relances|recherche|tout|mails|reponses [--essai] [--fois N] [--depuis AAAA-MM-JJ]
    lmagent.py --postuler [--reponses]          assistant de candidature par formulaire
    lmagent.py --maj-tableau [--voir]           mise à jour interactive du tableau
    lmagent.py --agent [--task "…" | --tache nom]   agent en chat / tâche automatique

Depuis le code, les anciens scripts (web/app.py, alternance/relances.py…) marchent toujours.
"""
import subprocess
import sys
from pathlib import Path

ICI = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for p in (ICI / "alternance" / "src", ICI / "alternance", ICI / "web" / "src", ICI / "web", ICI / "src", ICI):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

ROUTINES = ("relances", "recherche", "tout", "mails", "reponses")   # mails : mails reçus seulement
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


def sortie_utf8():
    """Sortie en UTF-8 (emojis du journal) et écrite ligne par ligne : sinon un fichier reçu de l'interface ou
    de la boucle est écrit en cp1252 (le premier emoji fait planter le script : l'exe compilé ignore
    PYTHONIOENCODING) et par paquets de 8 Ko (l'interface n'affiche plus le journal en temps réel)."""
    for flux in (sys.stdout, sys.stderr):
        if flux is not None and hasattr(flux, "reconfigure"):
            try:
                flux.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


def preparer_sortie(args):
    """Choisit où va la sortie quand l'exe tourne sans console, et la met en UTF-8."""
    if not sans_console():
        sortie_utf8()
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


def _fichier_de_sortie():
    """sys.stdout s'il correspond à un vrai fichier (à transmettre aux passages), sinon None (console : hérité)."""
    try:
        sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return None
    return sys.stdout


def routine(args):
    nom = _valeur(args, "--routine")
    if nom not in ROUTINES:
        sys.exit(f"Routine inconnue : {nom} (choisir parmi {', '.join(ROUTINES)})")
    essai = ["--essai"] if "--essai" in args else []
    if _valeur(args, "--depuis"):   # mails envoyés et reçus lus à partir de ce jour (AAAA-MM-JJ)
        essai += ["--depuis", _valeur(args, "--depuis")]
    try:
        fois = max(1, int(_valeur(args, "--fois", 1)))
    except ValueError:
        fois = 1
    import avancement   # avancement en direct (page Routines), routine programmée comprise
    avancement.commencer(nom, fois, essai="--essai" in args)
    code = 1
    try:
        code = _routine(nom, fois, essai)
    finally:
        avancement.finir(code)
    return code


def _routine(nom, fois, essai):
    if fois > 1:  # chaque passage dans un processus neuf (comme un lancement manuel)
        import os
        import boucle
        code = 0
        sortie = _fichier_de_sortie()
        ident = os.getpid()
        try:
            import avancement
            for i in range(fois):
                print(f"\n===== Passage {i + 1}/{fois} =====\n", flush=True)
                avancement.passage(i + 1, fois)
                # le passage écrit dans le MÊME fichier ouvert que la boucle (sinon chacun écrit à sa propre position
                # et les repères « Passage N » écrasent le début du journal) ; modèle et LM Studio restent ouverts
                # jusqu'au dernier passage (boucle.py)
                code = subprocess.call(commande_soi() + ["--routine", nom] + essai, stdout=sortie,
                                       stderr=subprocess.STDOUT if sortie else None,
                                       env=boucle.environnement(ident, i + 1, fois)) or code
                sys.stdout.flush()
        finally:
            boucle.nettoyer(ident)
        return code
    if nom == "reponses":   # lettre et réponses manquantes des candidatures La Bonne Alternance
        import reponses_lba
        return reponses_lba.main(essai=bool(essai))
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
    # fermeture pour une mise à jour : la tour n'est pas mise en veille (LMAgent se relance tout de suite)
    mise_a_jour.surveiller(routines.en_cours, fermer=lambda: icone_tache.quitter(par_l_utilisateur=False))
    app.lancer_interface()
    return 0


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    preparer_sortie(args)
    import sans_fenetre
    sans_fenetre.activer()   # sans console : pas de terminal qui clignote à chaque commande lancée
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
