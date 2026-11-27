"""Page Paramètres : menu à gauche. Chaque catégorie regroupe des sections de reglages.py (titres inchangés) ;
les réglages très techniques vont dans « Avancé » (avec le titre de leur section), les fichiers de signature dans
« Signatures ». Un réglage apparaît dans une seule catégorie (vérifié par les tests)."""

# (clé, icône, titre, sections de reglages.py) ; profil, signatures et compte ont aussi leurs formulaires à eux
CATEGORIES = [
    ("profil", "👤", "Mon profil", []),
    ("signatures", "✍️", "Signatures", []),
    ("candidatures", "📨", "Candidatures et relances", ["Candidatures et relances", "Candidatures faites ailleurs", "Fichiers"]),
    ("recherche", "🔎", "Recherche d'entreprises", ["La Bonne Alternance", "Alertes LinkedIn", "Sites des entreprises",
                                                    "Adresses mail"]),
    ("formulaire", "🎓", "Formulaire La Bonne Alternance", ["Formulaire La Bonne Alternance prérempli",
                                                               "Questions du formulaire La Bonne Alternance"]),
    ("messagerie", "📬", "Messagerie", ["Messagerie"]),
    ("modele", "🧠", "Modèle et tour", ["Rédaction par le modèle", "Agent et modèle", "Tour"]),
    ("interface", "🖥️", "Interface et compte", ["Interface", "Mises à jour"]),
    ("avance", "⚙️", "Avancé", []),
]
SIGNATURES = {"signature_html", "messagerie.imap.signature_html"}
AVANCES = {
    "sites.pages_max", "sites.attente_recherche_s", "sites.annuaires", "sites.mots_contact", "sites.pages_classiques",
    "adresses.domaines_perso", "adresses.prefixes_generiques", "alertes_linkedin.expediteurs",
    "la_bonne_alternance.demi_distance_km", "la_bonne_alternance.poids_min", "la_bonne_alternance.recherches_site_max",
    "outlook.chemins_exe", "outlook.attente_ouverture_s", "outlook.garde_minutes", "suivi_ailleurs.mots_postes",
    "interface.cache_lettres_minutes", "lms_local", "serveurs", "dossiers_autorises", "powershell_en_auto", "etapes_max",
    "gpu", "contexte", "afficher_reflexion", "mises_a_jour_depot", "npu_installation_auto",
}


def categorie_de(section, chemin):
    if chemin in SIGNATURES:
        return "signatures"
    if chemin in AVANCES:
        return "avance"
    return next((cle for cle, _, _, sections in CATEGORIES if section in sections), "avance")


def categories(sections):
    """sections : reglages_web.sections() -> [{cle, icone, titre, groupes: [(titre de section, [champ…])]}]."""
    res = {cle: {"cle": cle, "icone": icone, "titre": titre, "groupes": {}} for cle, icone, titre, _ in CATEGORIES}
    for titre_section, champs in sections:
        for c in champs:
            groupe = "Fichier de signature HTML (au lieu de la signature ci-dessus)" if c["chemin"] in SIGNATURES else titre_section
            res[categorie_de(titre_section, c["chemin"])]["groupes"].setdefault(groupe, []).append(c)
    return [{**c, "groupes": list(c["groupes"].items())} for c in res.values()]
