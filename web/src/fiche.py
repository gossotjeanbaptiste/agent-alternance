"""Fiche d'une entreprise de la page Suivi (bouton ✏️) : nom, poste, adresse, contacts, lien, source, notes
modifiables. Une ou plusieurs adresses mail (colonne Email, séparées par « ; ») : toutes servent au suivi des
réponses et reçoivent les relances."""
import re

import suivi_donnees

CHAMPS = ["Entreprise", "Poste", "Lieu", "Contact", "Email", "Téléphone", "Lien", "Source", "Notes"]


def modifier(n_ligne, entreprise, d):
    """Enregistre la fiche de la ligne n_ligne (entreprise : nom actuel, pour vérifier que c'est la bonne ligne).
    d : nouvelles valeurs (champs absents laissés tels quels). Renvoie (ok, message)."""
    from mails import verifier_adresses
    champs = {c: str(d[c]).strip() for c in CHAMPS if c in d and d[c] is not None}
    if "Entreprise" in champs and not champs["Entreprise"]:
        return False, "Le nom de l'entreprise ne peut pas être vide."
    if "Email" in champs:
        champs["Email"], invalides = verifier_adresses(champs["Email"])
        if invalides:
            return False, f"Adresse mail invalide : {', '.join(invalides)} (plusieurs adresses : sépare-les par « ; »)."
    if champs.get("Lien") and re.match(r"(?i)javascript:", champs["Lien"]):
        return False, "Lien invalide."
    if not champs:
        return False, "Rien à enregistrer."
    ok, message = suivi_donnees.modifier(n_ligne, entreprise, champs)
    return ok, (f"Fiche de {champs.get('Entreprise') or entreprise} enregistrée." if ok else message)
