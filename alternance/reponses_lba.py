"""Routine « Réponses La Bonne Alternance » : pour chaque candidature « À postuler (La Bonne Alternance) » du tableau,
écrit ce qui manque — les réponses aux trois questions du formulaire et, s'il le faut, la lettre — avec le modèle
(la tour, sinon ce PC). Rien n'est envoyé : tout s'affiche ensuite sur la page « À postuler ».

    python lmagent.py --routine reponses [--essai]      (ou bouton dans la page Routines de l'interface)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # modules internes (alternance/src)
import commun  # noqa: E402
import reponses  # noqa: E402
from commun import say  # noqa: E402
from tableau import LBA, Suivi  # noqa: E402


def main(essai=False):
    import agent
    import postuler
    commun.ESSAI = essai
    agent.log("===== ROUTINE RÉPONSES LA BONNE ALTERNANCE =====")
    t0 = time.time()
    s = Suivi(commun.chemin_tableau())
    lignes = [r for r in s.rows() if s.get(r, "Statut") == LBA and (s.get(r, "Lien") or "").strip()]
    say(f"🎓 {len(lignes)} candidature(s) à postuler sur La Bonne Alternance")
    lettres = postuler.lettres_des_brouillons()
    deja = reponses.lire()
    a_faire = []
    for r in lignes:
        lien = (s.get(r, "Lien") or "").strip()
        manque = reponses.manque(LBA, lien, bool(lettres.get(lien)), deja)
        if manque:
            a_faire.append((r, manque))
    if not a_faire:
        say("✅ Rien à écrire : toutes ont déjà leur lettre et leurs réponses.")
        return 0
    say(f"✍️ {len(a_faire)} à compléter{' (essai : rien ne sera enregistré)' if essai else ''}")
    faites = erreurs = 0
    for i, (r, manque) in enumerate(a_faire, 1):
        ent = s.get(r, "Entreprise")
        say(f"   [{i}/{len(a_faire)}] {ent} : {' et '.join(manque)}…")
        commun.etape("Réponses La Bonne Alternance", ent, i, len(a_faire))
        try:
            if "la lettre" in manque:
                postuler.ecrire_lettre(s, r)
            if "les réponses" in manque:
                postuler.reponses_de(s, r, deja)
            faites += 1
        except Exception as e:      # une entreprise en échec n'arrête pas les suivantes
            erreurs += 1
            say(f"   ⚠️ {ent} : non écrit ({e})")
    minutes = round((time.time() - t0) / 60)
    say(f"✅ Routine « réponses » terminée en {minutes} min : {faites} candidature(s) complétée(s)"
        + (f", {erreurs} en échec" if erreurs else "") + ". Tout est sur la page « À postuler ».")
    return 1 if erreurs and not faites else 0


if __name__ == "__main__":
    sys.exit(main("--essai" in sys.argv))
