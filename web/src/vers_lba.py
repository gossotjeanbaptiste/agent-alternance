"""Bouton « 🎓 Postuler par La Bonne Alternance » des candidatures « adresse à trouver » de la page À postuler :
l'entreprise vient de La Bonne Alternance (lien de sa fiche), ou elle y est cherchée au clic (SIRET, sinon nom autour
de son adresse : lba_recherche.py). La lettre du brouillon est gardée pour le formulaire, la candidature repasse en
« À postuler (La Bonne Alternance) », le brouillon sans adresse va à la corbeille, puis le modèle écrit les réponses
aux questions du formulaire (et la lettre s'il n'y en avait pas)."""
import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
from tableau import ADRESSE_A_TROUVER, LBA, Suivi


def fiche_lba(lien):
    """Vrai si le lien est une fiche La Bonne Alternance (là où se trouve le formulaire)."""
    lien = str(lien or "").strip()
    return lien.startswith("https://") and "labonnealternance" in lien


def possible(ligne):
    """Le bouton a-t-il un sens ? Fiche La Bonne Alternance connue, ou de quoi l'y chercher (SIRET, adresse)."""
    import lba_recherche
    return (fiche_lba(ligne.get("Lien")) or bool(lba_recherche.siret_de(ligne.get("Notes")))
            or bool(str(ligne.get("Lieu") or "").strip()))


def _chercher_fiche(s, row, entreprise):
    """Fiche La Bonne Alternance d'une candidature venue d'ailleurs : (lien, champs à noter) ou (None, raison)."""
    import lba_recherche
    notes = str(s.get(row, "Notes") or "")
    siret = lba_recherche.siret_de(notes)
    fiche, raison = lba_recherche.trouver(entreprise, siret, str(s.get(row, "Lieu") or "").strip())
    if not fiche:
        return None, raison
    champs = {"Lien": fiche["lien"]}
    if fiche["activite"] and "Activité :" not in notes:   # activité officielle : redonnée au modèle (NE_PAS_INVENTER)
        champs["Notes"] = " | ".join(x for x in (notes, f"Activité : {fiche['activite']}") if x)
    return fiche["lien"], champs


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
    if s.get(row, "Statut") != ADRESSE_A_TROUVER:
        return False, "Seules les candidatures « adresse à trouver » sont concernées."
    lien, champs = str(s.get(row, "Lien") or "").strip(), {}
    if not fiche_lba(lien):
        lien, champs = _chercher_fiche(s, row, entreprise)
        if not lien:
            return False, f"{entreprise} : {champs}. Cherche plutôt son adresse de contact."
    lettre = _lettre_du_brouillon(entreprise)
    if lettre:
        reponses.enregistrer_lettre(lien, lettre)
    ok, message = suivi_donnees.modifier(n_ligne, entreprise, {**champs, "Statut": LBA})
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
