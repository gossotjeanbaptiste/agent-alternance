"""Bouton « 🧾 Ouvrir le formulaire prérempli » de la page À postuler (candidatures La Bonne Alternance) :
la lettre, les réponses et le CV de la candidature sont mis dans le formulaire du site, ouvert dans Chrome."""
import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
from tableau import LBA, Suivi


def ouvrir_formulaire(n_ligne, entreprise):
    """Ouvre et remplit le formulaire de la ligne n_ligne. Renvoie (ok, message). N'envoie jamais rien."""
    import formulaire_lba
    import lettres
    import reponses
    s = Suivi(commun.chemin_tableau())
    row = next((r for r in s.rows() if r[0].row == n_ligne), None)
    if not row or str(s.get(row, "Entreprise")) != entreprise:
        return False, "Ligne introuvable (le tableau a changé) : recharge la page."
    lien = str(s.get(row, "Lien") or "").strip()
    if s.get(row, "Statut") != LBA or not lien.startswith("http"):
        return False, "Seules les candidatures par le formulaire La Bonne Alternance (avec un lien) sont concernées."
    try:
        les_lettres, sig = lettres.lettres_et_signature()
    except Exception:
        les_lettres, sig = {}, ""
    lettre = les_lettres.get(lien) or ""
    if lettre and sig:
        lettre = f"{lettre}\n\n{sig}"
    donnees = formulaire_lba.champs(lettre, reponses.lire().get(lien) or {})
    cv = formulaire_lba.choisir_cv(commun.pieces_jointes())
    try:
        ok, message = formulaire_lba.ouvrir_et_remplir(lien, donnees, cv)
    except Exception as e:      # Chrome absent, fermé en cours de route…
        return False, f"Formulaire non prérempli : {e}"
    manque = [quoi for quoi, present in (("la lettre", lettre), ("les réponses", donnees["reponses"])) if not present]
    if ok and manque:
        message += f" (pas encore de {' ni de '.join(manque)} : « ✍️ Écrire ce qui manque » d'abord, puis rouvre)"
    return ok, message
