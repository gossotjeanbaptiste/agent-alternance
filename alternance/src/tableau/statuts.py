"""Colonnes du tableau, statuts (avec leur couleur) et anciens noms de statut."""

COLS = ["Date ajout", "Entreprise", "Poste", "Lieu", "Source", "Lien", "Contact", "Email", "Téléphone",
        "Statut", "Date envoi", "Dernière action", "Relance prévue", "Nb relances",
        "Dernière réponse", "Notes"]
COLS_A_CONTACTER = ["Entreprise", "Poste", "Lieu", "Contact", "Email", "Lien", "Infos", "Traité", "Site"]
STATUTS = {  # statut -> couleur de fond
    "Brouillon": "FFF2CC", "Brouillon (adresse à trouver)": "FCE4D6",
    "À postuler (La Bonne Alternance)": "E2EFDA", "À postuler (formulaire du site)": "E2EFDA",
    "Candidaté (mail)": "DDEBF7", "Relance en brouillon": "FFF2CC", "Relance programmée": "DDEBF7", "Relancé": "BDD7EE",
    "Candidaté (La Bonne Alternance)": "DDEBF7", "Candidaté (formulaire du site)": "DDEBF7",
    "Candidaté (LinkedIn)": "DDEBF7", "Candidaté (autre canal)": "EDEDED",
    "Réponse à lire": "FFE699", "Candidature transmise": "E4DFEC", "Réponse positive": "C6EFCE",
    "Demande de disponibilités": "D6ECC0", "Entretien": "A9D08E",
    "Accepté": "70AD47", "Refus": "F4B6B6", "Adresse invalide": "FF9999", "Sans réponse": "D9D9D9",
    "Abandonné": "BFBFBF",
}
TRANSMISE = "Candidature transmise"   # réponse « j'ai fait suivre aux RH / au service » : suivie, plus relancée
# l'entreprise demande quand l'étudiant est disponible (appel, entretien à caler) : à lui de répondre, plus de relance
DISPONIBILITES = "Demande de disponibilités"
LBA = "À postuler (La Bonne Alternance)"
FORMULAIRE = "À postuler (formulaire du site)"
A_POSTULER = (LBA, FORMULAIRE)
ADRESSE_A_TROUVER = "Brouillon (adresse à trouver)"   # brouillon de mail sans destinataire
# tout ce que la page « À postuler » affiche (et que compte le tableau de bord), dans l'ordre de la page :
# formulaires, puis mails à envoyer, puis adresses à trouver
PAGE_A_POSTULER = (LBA, FORMULAIRE, "Brouillon", ADRESSE_A_TROUVER)
# candidature envoyée : par mail (suivie et relancée automatiquement) ou par un autre canal
MAIL = "Candidaté (mail)"
C_LBA = "Candidaté (La Bonne Alternance)"
C_FORMULAIRE = "Candidaté (formulaire du site)"
C_LINKEDIN = "Candidaté (LinkedIn)"
C_AUTRE = "Candidaté (autre canal)"
HORS_MAIL = (C_LBA, C_FORMULAIRE, C_LINKEDIN, C_AUTRE)


def ancien_statut(statut, notes, source=""):
    """Anciens noms de statut -> nouveaux (« Envoyé », « Candidaté (hors mail) »)."""
    if statut == "Envoyé":
        return MAIL
    if statut == "Candidaté (hors mail)":
        n = (notes or "").lower()
        via = n.split("candidature via", 1)[1] if "candidature via" in n else ""
        if via:
            return statut_par_canal(via)
        if "bonne alternance" in (source or "").lower():  # envoyée depuis la page « À postuler »
            return C_LBA
        return C_AUTRE
    return statut


def statut_par_canal(canal):
    """Statut « Candidaté (…) » d'après le canal saisi (« La Bonne Alternance », « site », « LinkedIn »…)."""
    c = (canal or "").lower()
    if "bonne" in c or "labonnealternance" in c or "lba" in c:
        return C_LBA
    if "linkedin" in c:
        return C_LINKEDIN
    if any(m in c for m in ("formulaire", "form ", "form contact", "site", "contact", "http")):
        return C_FORMULAIRE
    return C_AUTRE
