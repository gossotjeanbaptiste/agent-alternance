"""
Routine quotidienne de recherche d'alternance.

    python alternance\alternance.py              -> suivi + relances, puis nouvelles candidatures
    python alternance\alternance.py --relances   -> seulement suivi + relances   (= relances.py)
    python alternance\alternance.py --recherche  -> seulement nouvelles candidatures (= recherche.py)
    ajouter --essai pour tout simuler sans rien écrire

Organisation du code (modules internes dans alternance/src/) :
    commun.py        réglages partagés (config, profil, mode essai)
    jours.py         jours ouvrables, fériés, heures d'envoi
    modele.py        appels au modèle IA
    mails.py         outils sur les adresses / le texte
    tableau.py       tableau de suivi Excel
    messagerie.py    choix de la messagerie : outlook.py (Outlook classique) ou imap.py (Gmail…)
    suivi.py         mise à jour du suivi + relances
    sources.py       sources d'entreprises (liste perso, LinkedIn, La Bonne Alternance)
    candidatures.py  nouvelles candidatures
"""
import argparse
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # modules internes (alternance/src)
import commun  # noqa: E402
import reglages  # noqa: E402
from candidatures import nouvelles_candidatures  # noqa: E402
from commun import CFG, P, agent, say  # noqa: E402
from messagerie import nom_messagerie, ouvrir  # noqa: E402
from suivi import mettre_a_jour  # noqa: E402
from tableau import Suivi  # noqa: E402


def main(mode=None):
    """mode : "tout" (défaut), "relances" (suivi + relances) ou "recherche" (nouvelles candidatures)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--suivi", "--relances", action="store_true", dest="relances",
                    help="seulement suivi des réponses + relances")
    ap.add_argument("--recherche", action="store_true", help="seulement les nouvelles candidatures")
    ap.add_argument("--essai", action="store_true", help="ne rien écrire")
    a = ap.parse_args()
    commun.ESSAI = a.essai
    mode = mode or ("relances" if a.relances else "recherche" if a.recherche else "tout")

    agent.log(f"===== ROUTINE ALTERNANCE ({mode}) =====")
    t0 = datetime.now()
    agent.ensure_server()
    suivi = Suivi(P(CFG["tableau_suivi"]))

    # Garde-fou : si la LECTURE d'Outlook dépasse 10 min (connexion demandée, Outlook bloqué...),
    # on arrête proprement. Il est désactivé dès qu'Outlook a été lu (voir mettre_a_jour).
    def outlook_bloque():
        say(f"❌ {nom_messagerie()} ne répond pas depuis {reglages.valeur('outlook.garde_minutes')} min. Avec Outlook : ouvre l'Outlook classique, "
            "connecte-toi si demandé, attends la fin de la synchronisation, puis relance. "
            "Avec IMAP : vérifie ta connexion Internet.")
        agent.liberer_modele()  # os._exit saute le nettoyage automatique : on libère la VRAM avant
        os._exit(2)
    garde = int(reglages.valeur("outlook.garde_minutes"))
    commun.GARDE = threading.Timer(garde * 60, outlook_bloque)
    commun.GARDE.daemon = True
    commun.GARDE.start()
    ol = ouvrir()
    try:
        if mode in ("tout", "relances"):
            mettre_a_jour(suivi, ol)
            suivi.save()
        else:
            ol.recus(CFG["alertes_linkedin"]["jours"])  # lecture des alertes LinkedIn
            commun.GARDE.cancel()
        if mode in ("tout", "recherche"):
            nouvelles_candidatures(suivi, ol)
            suivi.save()
    finally:
        suivi.save()
    say(f"✅ Routine « {mode} » terminée en {(datetime.now() - t0).seconds // 60} min (modèle : {agent.SERVEUR}). "
        f"Les brouillons sont dans {nom_messagerie()}, le suivi dans le tableau Excel.")


if __name__ == "__main__":
    main()
