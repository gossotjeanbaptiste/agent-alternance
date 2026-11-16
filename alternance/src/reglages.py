"""Tous les réglages modifiables, décrits en un seul endroit.

Chaque réglage : fichier (« alternance » = alternance/donnees/config_alternance.json, « agent » = config.json),
chemin dans le JSON (« sites.pages_max »), libellé, type, valeur par défaut et aide.
- le code lit ses valeurs avec valeur("chemin") : la config si elle la contient, sinon la valeur par défaut ;
- la page Paramètres de l'interface affiche et enregistre ces réglages.

Types : entier, decimal, texte, oui_non, liste (une valeur par ligne), choix, secret (mot de passe / jeton),
json (structure plus complexe, ex. les villes).
"""

# Valeurs par défaut des listes (reprises du code d'origine)
DOMAINES_PERSO = ["gmail.com", "outlook.fr", "outlook.com", "hotmail.fr", "hotmail.com", "yahoo.fr", "yahoo.com",
                  "orange.fr", "free.fr", "laposte.net", "wanadoo.fr", "icloud.com", "live.fr", "sfr.fr"]
GENERIQUES = ["contact", "rh", "recrutement", "recrutements", "jobs", "job", "carriere", "carrieres", "emploi",
              "info", "infos", "hello", "bonjour", "accueil", "secretariat", "candidature", "candidatures", "drh",
              "admin", "direction", "talent", "talents"]
ANNUAIRES = ["societe.com", "pappers", "pagesjaunes", "kompass", "dnb.com", "linkedin", "facebook", "instagram",
             "twitter", "x.com", "youtube", "wikipedia", "mappy", "infogreffe", "verif.com", "manageo", "annuaire",
             "indeed", "welcometothejungle", "glassdoor", "labonnealternance", "france-travail", "pole-emploi",
             "hellowork", "findglocal", "corporama", "lefigaro", "google", "bing.com", "apple.com", "yelp",
             "tripadvisor", "infonet", "entreprises.lefigaro", "societeinfo", "score3", "ellisphere", "bfmtv",
             "francebleu", "elioplus", "superordi", "118000", "118712", "justacote", "cylex", "hoodspot", "doctrine"]
MOTS_CONTACT = ["contact", "nous-contacter", "contactez", "recrutement", "carriere", "carrieres", "emploi", "jobs",
                "join", "rejoindre", "candidature", "postuler", "mentions-legales", "a-propos", "about"]
PAGES_CLASSIQUES = ["/contact", "/nous-contacter", "/contact/", "/contact.html", "/recrutement", "/mentions-legales"]
NAF_ACCEPTES = ["62", "63.11", "63.12", "58.2", "26.1", "26.2", "26.3", "26.4", "26.5", "46.51", "61"]
OUTLOOK_EXE = [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
               r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE"]
QUESTIONS = {
    "motivations": ("Vos motivations : pourquoi souhaitez-vous rejoindre l'entreprise ?",
                    "pourquoi je souhaite rejoindre cette entreprise précisément (son activité, ce qui m'attire chez elle)"),
    "missions": ("Quelles missions souhaiteriez-vous accomplir au sein de l'entreprise ?",
                 "le poste visé, les missions que je souhaite accomplir et ma contribution concrète aux activités de l'entreprise"),
    "experiences": ("Vos expériences passées (stage, job, bénévolat) en lien avec le poste visé",
                    "mes expériences passées (stages, jobs, bénévolat, projets) en lien avec le poste visé, et ce qu'elles m'ont apporté"),
}


def _r(section, fichier, chemin, libelle, type_, defaut, aide="", choix=None, tour=False):
    return {"section": section, "fichier": fichier, "chemin": chemin, "libelle": libelle, "type": type_,
            "defaut": defaut, "aide": aide, "choix": choix or [], "tour": tour}


A, G = "alternance", "agent"
REGLAGES = [
    # --- candidatures et relances
    _r("Candidatures et relances", A, "mails_par_jour", "Nouvelles candidatures par lancement", "entier", 5),
    _r("Candidatures et relances", A, "relance_apres_jours", "Délai avant une relance (jours)", "entier", 8),
    _r("Candidatures et relances", A, "relances_max", "Relances max par entreprise", "entier", 2),
    _r("Candidatures et relances", A, "relances_max_par_jour", "Relances max par lancement", "entier", 5),
    _r("Candidatures et relances", A, "heure_envoi_relance", "Heure conseillée pour envoyer une relance", "texte", "09:30",
       "Format HH:MM. Affichée dans le journal et le tableau : c'est toi qui planifies l'envoi."),
    _r("Candidatures et relances", A, "fenetre_aleatoire_minutes", "Fenêtre aléatoire après cette heure (minutes)", "entier", 15),
    _r("Candidatures et relances", A, "jours_feries_alsace", "Jours fériés d'Alsace-Moselle", "oui_non", False,
       "Ajoute le Vendredi saint et le 26 décembre."),
    _r("Candidatures et relances", A, "domaines_ignores", "Domaines de ton école / employeur", "liste", [],
       "Leurs mails ne sont jamais comptés comme des réponses d'entreprise."),
    # --- rédaction par le modèle
    _r("Rédaction par le modèle", A, "reflexion", "Réflexion du modèle", "oui_non", False,
       "Le modèle « réfléchit » avant d'écrire : environ 10 fois plus lent."),
    _r("Rédaction par le modèle", A, "redaction.longueur_relance", "Longueur d'une relance", "texte", "60 à 110 mots"),
    _r("Rédaction par le modèle", A, "redaction.longueur_reponses", "Longueur des réponses aux questions",
       "texte", "4 à 6 phrases (environ 600 à 900 caractères)"),
    *[r for cle, (titre, consigne) in QUESTIONS.items() for r in (
        _r("Questions du formulaire La Bonne Alternance", A, f"redaction.questions.{cle}.titre",
           f"Question « {cle} » : intitulé affiché", "texte", titre),
        _r("Questions du formulaire La Bonne Alternance", A, f"redaction.questions.{cle}.consigne",
           f"Question « {cle} » : consigne pour le modèle", "texte", consigne))],
    # --- fichiers
    _r("Fichiers", A, "tableau_suivi", "Tableau de suivi (chemin)", "texte", "",
       "Vide = suivi_alternance.xlsx dans le dossier de données (créé automatiquement)."),
    _r("Fichiers", A, "pieces_jointes", "Pièces jointes des candidatures (chemins)", "liste", [],
       "CV, calendrier d'alternance… un chemin par ligne."),
    # --- messagerie
    _r("Messagerie", A, "messagerie.type", "Messagerie utilisée", "choix", "outlook",
       "Outlook classique ou Gmail / IMAP.", choix=["outlook", "imap"]),
    _r("Messagerie", A, "messagerie.imap.serveur", "Serveur IMAP", "texte", "imap.gmail.com"),
    _r("Messagerie", A, "messagerie.imap.port", "Port IMAP", "entier", 993),
    _r("Messagerie", A, "messagerie.imap.adresse", "Adresse de la boîte IMAP", "texte", ""),
    _r("Messagerie", A, "messagerie.imap.mot_de_passe_app", "Mot de passe d'application IMAP", "secret", "",
       "Pour Gmail : mot de passe d'application (myaccount.google.com/apppasswords), jamais ton mot de passe normal."),
    _r("Messagerie", A, "messagerie.imap.signature_html", "Signature HTML pour Gmail (chemin)", "texte", "",
       "Vide = signature construite depuis la page Paramètres (si « ajouter la signature » est coché)."),
    _r("Messagerie", A, "signature_html", "Signature HTML pour Outlook (chemin)", "texte", ""),
    _r("Messagerie", A, "outlook.chemins_exe", "Emplacements possibles d'OUTLOOK.EXE", "liste", OUTLOOK_EXE),
    _r("Messagerie", A, "outlook.attente_ouverture_s", "Attente après l'ouverture d'Outlook (secondes)", "entier", 20),
    _r("Messagerie", A, "outlook.garde_minutes", "Arrêt si la messagerie ne répond plus après (minutes)", "entier", 10),
    # --- La Bonne Alternance
    _r("La Bonne Alternance", A, "la_bonne_alternance.actif", "Utiliser La Bonne Alternance", "oui_non", True),
    _r("La Bonne Alternance", A, "la_bonne_alternance.jeton_api", "Jeton API", "secret", "",
       "Gratuit : compte sur api.apprentissage.beta.gouv.fr."),
    _r("La Bonne Alternance", A, "la_bonne_alternance.codes_rome", "Métiers recherchés (codes ROME)", "liste", []),
    _r("La Bonne Alternance", A, "la_bonne_alternance.rayon_km", "Rayon autour de chaque ville (km)", "entier", 25),
    _r("La Bonne Alternance", A, "la_bonne_alternance.naf_acceptes", "Activités acceptées (codes NAF)", "liste", NAF_ACCEPTES,
       "Candidatures spontanées seulement pour ces activités (un préfixe suffit : 62 couvre 62.01Z…). "
       "Les entreprises écartées sont listées dans entreprises_refusees.csv."),
    _r("La Bonne Alternance", A, "la_bonne_alternance.centre", "Ville de référence pour les poids", "json",
       {"nom": "", "lat": 0, "lon": 0}),
    _r("La Bonne Alternance", A, "la_bonne_alternance.villes_prioritaires", "Villes prioritaires", "liste", []),
    _r("La Bonne Alternance", A, "la_bonne_alternance.demi_distance_km", "Le poids est divisé par 2 tous les (km)", "entier", 30),
    _r("La Bonne Alternance", A, "la_bonne_alternance.poids_min", "Poids minimal d'une ville", "decimal", 0.05),
    _r("La Bonne Alternance", A, "la_bonne_alternance.villes", "Villes de recherche", "json", [],
       "Liste de {\"nom\", \"lat\", \"lon\"} (un \"poids\" écrit à la main passe avant le calcul)."),
    _r("La Bonne Alternance", A, "la_bonne_alternance.recherches_site_max", "Sites d'entreprise fouillés par passage", "entier", 30),
    # --- sites des entreprises
    _r("Sites des entreprises", A, "sites.pages_max", "Pages lues par site", "entier", 6),
    _r("Sites des entreprises", A, "sites.verifier_france", "N'utiliser que des sites d'entreprises en France", "oui_non",
       True, "Écarte les sites d'un autre pays (.lu, .be, .ch, .us…) ; un site en .com / .net… doit montrer une preuve "
             "française : code postal ou ville de l'entreprise, téléphone français, SIRET / RCS."),
    _r("Sites des entreprises", A, "sites.attente_recherche_s", "Pause entre deux recherches web (secondes)", "decimal", 4),
    _r("Sites des entreprises", A, "sites.annuaires", "Sites ignorés (annuaires, réseaux sociaux…)", "liste", ANNUAIRES),
    _r("Sites des entreprises", A, "sites.mots_contact", "Mots repérant une page contact / recrutement", "liste", MOTS_CONTACT),
    _r("Sites des entreprises", A, "sites.pages_classiques", "Pages essayées sur chaque site", "liste", PAGES_CLASSIQUES),
    # --- adresses
    _r("Adresses mail", A, "adresses.domaines_perso", "Messageries grand public", "liste", DOMAINES_PERSO,
       "Jamais prises pour le domaine d'une entreprise."),
    _r("Adresses mail", A, "adresses.prefixes_generiques", "Débuts d'adresse génériques (contact@, rh@…)", "liste", GENERIQUES,
       "Une adresse générique donne un mail plus formel (« Madame, Monsieur »)."),
    # --- alertes LinkedIn
    _r("Alertes LinkedIn", A, "alertes_linkedin.actif", "Lire les alertes emploi LinkedIn", "oui_non", True),
    _r("Alertes LinkedIn", A, "alertes_linkedin.expediteurs", "Expéditeurs des alertes", "liste", []),
    _r("Alertes LinkedIn", A, "alertes_linkedin.jours", "Alertes des N derniers jours", "entier", 3),
    # --- interface
    _r("Interface", A, "interface.cache_lettres_minutes", "Relecture des lettres de la page À postuler (minutes)", "entier", 5),
    _r("Interface", A, "interface.passages_max", "Passages max d'une routine", "entier", 50),
    # --- agent et modèle (config.json)
    _r("Agent et modèle", G, "utiliser_tour", "Utiliser un deuxième PC (la tour) pour faire tourner l'IA", "oui_non", False,
       "Décoché : l'IA tourne sur ce PC uniquement, la page et les réglages de la tour sont cachés."),
    _r("Agent et modèle", G, "modele", "Modèle LM Studio", "texte", "qwen/qwen3.5-9b"),
    _r("Agent et modèle", G, "contexte", "Taille du contexte", "entier", 16384),
    _r("Agent et modèle", G, "gpu", "Moteur sur ce PC", "choix", "auto", choix=["auto", "cuda", "vulkan", "cpu"]),
    _r("Agent et modèle", G, "reflexion", "Réflexion du modèle (agent)", "oui_non", False),
    _r("Agent et modèle", G, "afficher_reflexion", "Afficher la réflexion", "oui_non", False),
    _r("Agent et modèle", G, "decharger_a_la_fin", "Décharger le modèle à la fin", "oui_non", True),
    _r("Agent et modèle", G, "fermer_lmstudio_apres", "Refermer LM Studio s'il a été ouvert par le script", "oui_non", True),
    _r("Agent et modèle", G, "lms_local", "Chemin de lms.exe sur ce PC", "texte", "~/.lmstudio/bin/lms.exe"),
    _r("Agent et modèle", G, "serveurs", "Serveurs LM Studio (dans l'ordre)", "json", [{"nom": "ce PC", "url": "local"}]),
    _r("Agent et modèle", G, "dossiers_autorises", "Dossiers accessibles à l'agent", "liste", []),
    _r("Agent et modèle", G, "powershell_en_auto", "PowerShell dans les tâches automatiques", "oui_non", False, "Risqué."),
    _r("Agent et modèle", G, "etapes_max", "Actions max par demande", "entier", 20),
    # --- mises à jour (version installée)
    _r("Mises à jour", G, "mises_a_jour_auto", "Installer automatiquement les mises à jour", "oui_non", True,
       "Version installée : au lancement (puis toutes les 6 h), la dernière version publiée est installée sans rien demander."),
    _r("Mises à jour", G, "mises_a_jour_depot", "Dépôt GitHub des versions publiées", "texte",
       "gossotjeanbaptiste/agent-alternance"),
    # --- tour (branche main seulement)
    *[_r("Tour", G, f"tour.{c}", l, t, d, a, tour=True) for c, l, t, d, a in (
        ("mac", "Adresse MAC (Ethernet) de la tour", "texte", "", "Pour le Wake-on-LAN."),
        ("broadcast", "Adresse de diffusion du réseau local", "texte", "192.168.1.255", ""),
        ("ssh", "Accès SSH (utilisateur@nom-de-la-tour)", "texte", "", ""),
        ("url_lmstudio", "Adresse du serveur LM Studio de la tour", "texte", "", ""),
        ("ssh_lan", "Accès SSH par le réseau local (secours)", "texte", "", ""),
        ("attente_reveil_s", "Attente max du réveil (secondes)", "entier", 150, ""),
        ("veille_apres", "Remettre la tour en veille à la fin", "oui_non", False, "Seulement si c'est le script qui l'a réveillée."),
        ("port_serveur", "Port du serveur LM Studio sur la tour", "entier", 1235, ""),
        ("lms_tour", "Chemin de lms.exe sur la tour", "texte", "", ""),
        ("tailscale_tour", "Chemin de tailscale.exe sur la tour", "texte", r"C:\Program Files\Tailscale\tailscale.exe", ""),
        ("tailscale_local", "Chemin de tailscale.exe sur ce PC", "texte", r"C:\Program Files\Tailscale\tailscale.exe", ""),
        ("fermer_lmstudio_apres", "Refermer LM Studio sur la tour s'il a été ouvert par le script", "oui_non", True, ""),
        ("verifier_gpu", "Laisser la tour tranquille si sa carte graphique est occupée", "oui_non", True, ""),
        ("vram_libre_min_mo", "Mémoire graphique libre nécessaire (Mo)", "entier", 7000, ""),
        ("gpu_utilisation_max", "Utilisation max de la carte (%)", "entier", 40, ""),
        ("wol_internet.hote", "Adresse publique de ta box (réveil depuis l'extérieur)", "texte", "", ""),
        ("wol_internet.ports", "Ports UDP du Wake-on-LAN", "liste", [9, 7], ""))],
]

PAR_CHEMIN = {(r["fichier"], r["chemin"]): r for r in REGLAGES}


def lire_chemin(donnees, chemin, defaut=None):
    """Valeur d'un chemin « a.b.c » dans un dictionnaire, ou defaut si absent."""
    for cle in chemin.split("."):
        if not isinstance(donnees, dict) or cle not in donnees:
            return defaut
        donnees = donnees[cle]
    return donnees


def ecrire_chemin(donnees, chemin, valeur):
    *parents, dernier = chemin.split(".")
    for cle in parents:
        donnees = donnees.setdefault(cle, {})
    donnees[dernier] = valeur


def valeur(chemin):
    """Réglage de la routine (config_alternance.json), ou sa valeur par défaut."""
    import commun
    return lire_chemin(commun.CFG, chemin, PAR_CHEMIN[(A, chemin)]["defaut"])
