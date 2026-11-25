"""Bouton « 🧾 Ouvrir le formulaire prérempli » de la page À postuler (candidatures La Bonne Alternance) :
la lettre, les réponses et le CV de la candidature sont mis dans le formulaire du site, dans Chrome.
Deux façons (réglage « la_bonne_alternance.ouverture ») : l'extension LMAgent dans le Chrome habituel
(extension_lba.py), ou une fenêtre Chrome à part pilotée par LMAgent (formulaire_lba_chrome.py).
Chrome absent du PC : la page demande dans quel navigateur ouvrir (chrome/navigateurs.py) ; Edge, Brave… sont
pilotés comme Chrome, Firefox et le navigateur par défaut ouvrent seulement la fiche (lettre copiée)."""
import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
import reglages
from tableau import LBA, Suivi

EXTENSION = "mon Chrome (extension LMAgent)"


def _donnees(lien):
    """(données du formulaire, CV choisi, remarque sur le CV)."""
    import formulaire_lba
    import lettres
    import reponses
    try:
        les_lettres, sig = lettres.lettres_et_signature()
    except Exception:
        les_lettres, sig = {}, ""
    lettre = les_lettres.get(lien) or ""
    if lettre and sig:
        lettre = f"{lettre}\n\n{sig}"
    donnees = formulaire_lba.champs(lettre, reponses.lire().get(lien) or {})
    cv, remarque = formulaire_lba.cv_du_formulaire()
    donnees["cv"] = formulaire_lba.cv_pour_le_navigateur(cv)
    return donnees, remarque


def ouvrir_formulaire(n_ligne, entreprise, hote="127.0.0.1:8765", navigateur=None):
    """Ouvre et remplit le formulaire de la ligne n_ligne. N'envoie jamais rien.
    Renvoie (ok, message, extra) ; extra : {"navigateurs": [...]} quand Chrome est absent et qu'aucun navigateur
    n'est choisi (la page demande lequel), {"lettre": ...} quand le navigateur choisi ne peut pas être prérempli."""
    import chrome
    from chrome import navigateurs
    s = Suivi(commun.chemin_tableau())
    row = next((r for r in s.rows() if r[0].row == n_ligne), None)
    if not row or str(s.get(row, "Entreprise")) != entreprise:
        return False, "Ligne introuvable (le tableau a changé) : recharge la page.", {}
    lien = str(s.get(row, "Lien") or "").strip()
    if s.get(row, "Statut") != LBA or not lien.startswith("http"):
        return False, "Seules les candidatures par le formulaire La Bonne Alternance (avec un lien) sont concernées.", {}
    if not navigateur and not chrome.trouver_chrome():
        return False, "Google Chrome introuvable sur ce PC : choisis un autre navigateur.",             {"navigateurs": navigateurs.installes()}
    navigateur = navigateurs.reel(navigateur) if navigateur else None   # « par défaut » : Opera GX, Edge…
    donnees, remarque = _donnees(lien)
    extra = {}
    port = int(hote.rsplit(":", 1)[1]) if ":" in hote else 80
    extension = reglages.valeur("la_bonne_alternance.ouverture") == EXTENSION
    try:
        if navigateur and extension and navigateurs.chromium(navigateur):
            import extension_lba        # extension LMAgent installée dans ce navigateur (Opera GX, Edge…)
            extension_lba.ouvrir_dans_chrome(lien, extension_lba.deposer(donnees), port, navigateur)
            extra["lettre"] = donnees["applicant_message"]
            ok, message = True, (f"Fiche ouverte dans {navigateurs.nom(navigateur)} : l'extension LMAgent remplit le "
                                 "formulaire (rien ne se remplit ? installe-la dans ce navigateur, voir l'aide en haut "
                                 "de la page" + ("; la lettre est aussi copiée" if extra["lettre"] else "")
                                 + "). Relis puis envoie toi-même, et enfin « ✅ Envoyée » ici")
        elif navigateur and not navigateurs.chromium(navigateur):
            navigateurs.ouvrir_page(navigateur, lien)
            extra["lettre"] = donnees["applicant_message"]
            ok, message = True, (f"Fiche ouverte dans {navigateurs.nom(navigateur)} : le préremplissage ne marche "
                                 "qu'avec Chrome, Edge, Brave, Vivaldi, Opera ou Opera GX. Remplis le formulaire à la main"
                                 + (" (lettre copiée : Ctrl+V)" if extra["lettre"] else "")
                                 + ", envoie-le toi-même, puis « ✅ Envoyée » ici")
        elif navigateur:
            import formulaire_lba_chrome
            ok, message = formulaire_lba_chrome.ouvrir_et_remplir(lien, donnees, navigateur)
        elif extension:
            import extension_lba
            extension_lba.ouvrir_dans_chrome(lien, extension_lba.deposer(donnees), port)
            ok, message = True, ("Fiche ouverte dans ton Chrome : l'extension LMAgent remplit le formulaire (rien ne "
                                 "se remplit ? installe l'extension, voir l'aide en haut de la page). Relis puis "
                                 "envoie toi-même, et enfin « ✅ Envoyée » ici")
        else:
            import formulaire_lba_chrome
            ok, message = formulaire_lba_chrome.ouvrir_et_remplir(lien, donnees)
    except Exception as e:      # navigateur fermé en cours de route…
        return False, f"Formulaire non prérempli : {e}", {}
    manque = [quoi for quoi, present in (("la lettre", donnees["applicant_message"]),
                                         ("les réponses", donnees["reponses"])) if not present]
    if ok and manque:
        message += f" (pas encore de {' ni de '.join(manque)} : « ✍️ Écrire ce qui manque » d'abord, puis rouvre)"
    if remarque:
        message += f" (Attention : {remarque}.)"
    return ok, message, extra
