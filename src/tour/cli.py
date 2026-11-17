"""Ligne de commande de la tour : python src\\tour <commande> (liste dans la description du paquet)."""
import tour
from tour import T


def _confirmer(question, args):
    if "--oui" in args:
        return True
    return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y")


def _etat():
    def ok(b):
        return "✅ joignable" if b else "❌ injoignable"
    print(f"LM Studio de la tour         : {ok(tour.lmstudio_ok())}")
    print(f"SSH de la tour (Tailscale)   : {ok(tour.ssh_ok())}")
    if T.get("ssh_lan"):
        print(f"SSH de la tour (réseau local): {ok(tour.ssh_lan_ok())}")


def _fermer_lmstudio():
    tour.LMSTUDIO_OUVERT_PAR_SCRIPT = True
    tour.fermer_lmstudio_si_ouvert()


def _tailscale():
    tour.tailscale_local()
    if not tour.ssh_ok():
        tour.relancer_tailscale_tour()


def main(args):
    if not args or args[0] in ("-h", "--help", "aide"):
        print(tour.__doc__)
        return
    cmd, delai = args[0], 0 if "--maintenant" in args else 60
    simples = {"etat": _etat, "reveiller": tour.reveiller, "serveur": tour.demarrer_serveur,
               "fermer-lmstudio": _fermer_lmstudio, "tailscale": _tailscale, "annuler": tour.annuler}
    a_confirmer = {"veille": ("Mettre la tour en veille ?", tour.veille),
                   "eteindre": ("Éteindre la tour ?", lambda: tour.eteindre(delai)),
                   "redemarrer": ("Redémarrer la tour ?", lambda: tour.redemarrer(delai))}
    if cmd in simples:
        simples[cmd]()
    elif cmd in a_confirmer:
        question, action = a_confirmer[cmd]
        if _confirmer(question, args):
            action()
    else:
        print(f"Commande inconnue : {cmd}\n{tour.__doc__}")
