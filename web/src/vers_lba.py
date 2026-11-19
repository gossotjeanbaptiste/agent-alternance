"""Bouton « 🎓 Postuler par La Bonne Alternance » des candidatures « adresse à trouver » de la page À postuler (quand
l'entreprise vient de La Bonne Alternance) : la lettre du brouillon est gardée pour le formulaire, la candidature
repasse en « À postuler (La Bonne Alternance) », le brouillon sans adresse va à la corbeille, puis le modèle écrit les
réponses aux questions du formulaire (et la lettre s'il n'y en avait pas)."""
import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
from tableau import ADRESSE_A_TROUVER, LBA, Suivi


def fiche_lba(lien):
    """Vrai si le lien est une fiche La Bonne Alternance (là où se trouve le formulaire)."""
    lien = str(lien or "").strip()
    return lien.startswith("https://") and "labonnealternance" in lien


def _lettre_du_brouillon(entreprise):
    """Lettre du brouillon « adresse à trouver » de l'entreprise (sans la signature), ou ""."""
    import lettres
    import postuler
    from mails import adresse_a_trouver
    try:
        les_lettres, _ = lettres.lettres_et_signature()
    except Exception:
        return ""
    lettre = (les_lettres.get(adresse_a_trouver(entreprise))
              or lettres.lettre_sans_destinataire(entreprise, les_lettres.get(postuler.SANS_DESTINATAIRE) or []))
    return postuler.nettoyer(lettre) if lettre else ""


def passer_par_lba(n_ligne, entreprise):
    """Repasse la candidature par le formulaire La Bonne Alternance et fait écrire ce qui manque. Renvoie (ok, message)."""
    import lettres
    import redaction
    import reponses
    import suivi_donnees
    from mails import adresse_a_trouver
    s = Suivi(commun.chemin_tableau())
    row = next((r for r in s.rows() if r[0].row == n_ligne), None)
    if not row or str(s.get(row, "Entreprise")) != entreprise:
        return False, "Ligne introuvable (le tableau a changé) : recharge la page."
    lien = str(s.get(row, "Lien") or "").strip()
    if s.get(row, "Statut") != ADRESSE_A_TROUVER or not fiche_lba(lien):
        return False, "Seules les candidatures « adresse à trouver » venues de La Bonne Alternance sont concernées."
    lettre = _lettre_du_brouillon(entreprise)
    if lettre:
        reponses.enregistrer_lettre(lien, lettre)
    ok, message = suivi_donnees.modifier(n_ligne, entreprise, {"Statut": LBA})
    if not ok:
        return False, message
    morceaux = [f"{entreprise} : repassée par La Bonne Alternance"
                + (" (lettre du brouillon gardée)" if lettre else "")]
    if lettre:      # la lettre est à l'abri dans reponses_lba.json : le brouillon sans adresse ne sert plus
        morceaux.append(lettres.supprimer_brouillons(adresse_a_trouver(entreprise)))
    lettres.CACHE["quand"] = 0
    ok_ecrit, ecrit = redaction.ecrire_ce_qui_manque(n_ligne, entreprise)
    morceaux.append(ecrit if ok_ecrit else f"{ecrit} (clique « ✍️ Écrire ce qui manque » plus tard)")
    return True, " ".join(m for m in morceaux if m)
