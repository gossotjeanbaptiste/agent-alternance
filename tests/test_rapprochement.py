"""Rapprochement d'un mail reçu avec sa candidature (alternance/src/rapprochement.py) et suivi des réponses
des candidatures faites autrement qu'en mail. Messagerie et modèle simulés."""
from datetime import date, timedelta

import pytest

import rapprochement
import suivi
from tableau import C_FORMULAIRE, C_LINKEDIN, MAIL

AUJ = date.today()


@pytest.mark.parametrize("entreprise, mots", [
    ("Forgeval Dev", ["forgeval"]), ("Groupe France Services", []), ("Comptanova", ["comptanova"]),
    ("Société Générale Informatique", ["generale"]),
])
def test_mots_du_nom(entreprise, mots):
    assert rapprochement.mots_du_nom(entreprise) == mots


def test_mots_distinctifs_partages_ecartes():
    d = rapprochement.mots_distinctifs(["Atelier Numérique Lyon", "Atelier Bois", "Forgeval Dev"])
    assert d["forgevaldev"] == {"forgeval"}
    assert "atelier" not in d["ateliernumeriquelyon"]                 # partagé par deux entreprises


@pytest.mark.parametrize("expediteur, adresse, domaine_propre, distinctifs, attendu", [
    ("hello@comptanova.com", "hello@comptanova.com", True, set(), True),            # 1. même adresse
    ("support@comptanova.com", "hello@comptanova.com", True, set(), True),             # 2. même domaine
    ("support@comptanova.on.crisp.email", "hello@comptanova.com", True, set(), True),  # 3. outil de support à son nom
    ("rh@forgeval-dev.recruitee.com", "contact@forgeval-dev.fr", True, set(), True),
    ("support@comptanova.on.crisp.email", "hello@comptanova.com", False, set(), False),  # domaine partagé : non
    ("x@autre.on.crisp.email", "hello@comptanova.com", True, set(), False),
    ("marc.forgeval@gmail.com", "contact@forgeval-dev.fr", True, {"forgeval"}, True),   # 4. mot distinctif
    ("marc.forgeval@gmail.com", "", False, {"forgeval"}, True),                # candidature sans adresse
    ("jean.dupont@gmail.com", "contact@forgeval-dev.fr", True, {"forgeval"}, False),
    ("acmeo@myworkday.com", "", False, {"acmeo"}, True),                      # outil de recrutement
    ("pas une adresse", "hello@comptanova.com", True, set(), False),
])
def test_correspond(expediteur, adresse, domaine_propre, distinctifs, attendu):
    assert rapprochement.correspond(expediteur, adresse, domaine_propre, distinctifs) is attendu


# --- preuves dans le contenu du mail (signature) -------------------------------------------------------
SIGNATURE = """Bonjour,
Merci pour votre candidature, nous ne recrutons pas d'alternant cette année.
--
Marc Forgeval
Forgeval Dev — 12 rue de la République, 69002 Lyon
Tél. : 04 72 11 22 33 — www.forgeval-dev.fr"""


@pytest.mark.parametrize("donnees, attendu", [
    ({"adresse": "contact@forgeval-dev.fr"}, ["domaine forgeval-dev.fr"]),
    ({"site": "https://www.forgeval-dev.fr/contact"}, ["domaine forgeval-dev.fr"]),
    ({"telephone": "+33 4 72 11 22 33"}, ["téléphone +33 4 72 11 22 33"]),
    ({"lieu": "12 rue de la République 69002 Lyon"}, ["nom et code postal 69002"]),
    ({"lieu": "Lyon"}, ["nom et ville"]),
    ({"telephone": "04 72 99 99 99", "lieu": "38000 Grenoble"}, []),          # rien qui corresponde
    ({"adresse": "rh@gmail.com"}, []),                                       # messagerie grand public : pas une preuve
])
def test_preuves_dans_le_mail(donnees, attendu):
    assert rapprochement.preuves_dans_le_mail(SIGNATURE, "Forgeval Dev", **donnees) == attendu


def test_nom_seul_ne_suffit_pas():
    """Le nom cité sans adresse ni téléphone (ex. dans la lettre citée) ne prouve rien à lui seul."""
    assert rapprochement.preuves_dans_le_mail("Re: votre candidature chez Forgeval Dev", "Forgeval Dev",
                                              lieu="69002 Lyon") == []


def test_domaine_cite_dans_un_autre_mot_ignore():
    assert rapprochement.preuves_dans_le_mail("voir notre-forgeval-dev.fr.example", "X",
                                              adresse="a@forgeval-dev.fr") == []


# --- dans le suivi ------------------------------------------------------------------------------------
def ajouter(tableau, **v):
    v.setdefault("Date envoi", AUJ - timedelta(days=5))
    v.setdefault("Dernière action", AUJ - timedelta(days=5))
    tableau.add(**v)
    tableau.save()


def recu(de, sujet="Re: candidature", corps="Bonjour", jours=1, classe="IPM.Note"):
    from datetime import datetime
    return {"de": de, "sujet": sujet, "corps": corps, "date": datetime.now() - timedelta(days=jours), "classe": classe}


def ligne(tableau, entreprise):
    """Ligne du tableau en mémoire (mettre_a_jour modifie le tableau ; la routine l'enregistre ensuite)."""
    r = next(r for r in tableau.rows() if tableau.get(r, "Entreprise") == entreprise)
    return {c: tableau.get(r, c) for c in tableau.h}


def test_reponse_d_un_outil_de_support(tableau, messagerie, faux_modele):
    """Comptanova répond depuis Crisp (…@comptanova.on.crisp.email) : la candidature est mise à jour."""
    ajouter(tableau, Entreprise="Comptanova", Email="hello@comptanova.com", Statut=MAIL,
            **{"Relance prévue": AUJ + timedelta(days=5)})
    faux_modele.reponses_json = [{"type": "transmise", "resume": "Transmise au responsable"}]
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("support@comptanova.on.crisp.email")]), relancer=False)
    assert ligne(tableau, "Comptanova")["Statut"] == "Candidature transmise"


def test_reponse_a_une_candidature_par_formulaire(tableau, messagerie, faux_modele):
    """Candidature par le formulaire du site, réponse depuis une adresse personnelle : refus noté, pas de relance,
    et un vieil avis de non-remise vers l'adresse de contact ne la marque pas « adresse invalide »."""
    ajouter(tableau, Entreprise="Forgeval Dev", Email="contact@forgeval-dev.fr", Statut=C_FORMULAIRE)
    faux_modele.reponses_json = [{"type": "refus", "resume": "Pas de poste"}]
    ndr = recu("postmaster@outlook.com", "Non remis : candidature", "contact@forgeval-dev.fr introuvable", jours=2)
    ol = messagerie(recus=[ndr, recu("marc.forgeval@gmail.com", "Recrutement / Candidature")])
    suivi.mettre_a_jour(tableau, ol)
    l = ligne(tableau, "Forgeval Dev")
    assert l["Statut"] == "Refus" and "[refus]" in l["Dernière réponse"] and ol.deposes == []


def test_candidature_linkedin_sans_adresse(tableau, messagerie, faux_modele):
    ajouter(tableau, Entreprise="acmeo", Statut=C_LINKEDIN, Source="LinkedIn")
    faux_modele.reponses_json = [{"type": "automatique", "resume": "Candidature reçue"}]
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("acmeo@myworkday.com", "Thank you for Applying")]),
                        relancer=False)
    l = ligne(tableau, "acmeo")
    assert l["Statut"] == C_LINKEDIN and "[automatique]" in l["Dernière réponse"]   # accusé : statut inchangé


def test_reconnu_par_la_signature(tableau, messagerie, faux_modele, capsys):
    """Réponse d'une adresse sans rapport (secrétariat perso) : la signature (téléphone) confirme l'entreprise."""
    ajouter(tableau, Entreprise="Boîte Discrète", Email="contact@boite-discrete.fr", Statut=MAIL,
            Téléphone="04 72 11 22 33", **{"Relance prévue": AUJ + timedelta(days=5)})
    ajouter(tableau, Entreprise="Autre Société", Email="rh@autre-societe.fr", Statut=MAIL)
    faux_modele.reponses_json = [{"type": "entretien", "resume": "Entretien proposé"}]
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("secretariat.direction@orange.fr", "Votre candidature",
                                                        "Bonjour, venez lundi.\n--\nTél. 04.72.11.22.33")]),
                        relancer=False)
    assert ligne(tableau, "Boîte Discrète")["Statut"] == "Entretien"
    assert ligne(tableau, "Autre Société")["Dernière réponse"] in (None, "")
    assert "🔎 Boîte Discrète : mail de secretariat.direction@orange.fr reconnu grâce à son contenu (téléphone" \
        in capsys.readouterr().out


def test_contenu_ambigu_aucune_attribution(tableau, messagerie, faux_modele):
    """Le mail cite deux entreprises du tableau (même ville, deux noms) : dans le doute, aucune."""
    ajouter(tableau, Entreprise="Alpha Logiciel", Lieu="69002 Lyon", Statut=C_FORMULAIRE)
    ajouter(tableau, Entreprise="Beta Réseaux", Lieu="69002 Lyon", Statut=C_FORMULAIRE)
    faux_modele.reponses_json = [{"type": "refus", "resume": "Non"}]
    corps = "Alpha Logiciel et Beta Reseaux, 69002 Lyon, vous remercient."
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("forum@salon-emploi.fr", "Suite au salon", corps)]),
                        relancer=False)
    assert ligne(tableau, "Alpha Logiciel")["Dernière réponse"] in (None, "")
    assert ligne(tableau, "Beta Réseaux")["Dernière réponse"] in (None, "")


def test_mail_d_une_autre_entreprise_du_tableau_pas_par_le_contenu(tableau, messagerie, faux_modele):
    """Un mail venant du domaine d'une entreprise du tableau qui cite le téléphone d'une autre : pas attribué à l'autre."""
    ajouter(tableau, Entreprise="Cible", Email="rh@cible.fr", Statut=MAIL, Téléphone="04 72 11 22 33")
    ajouter(tableau, Entreprise="Voisin", Email="rh@voisin.fr", Statut="Refus")
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("jean@voisin.fr", "Info", "appelez le 04 72 11 22 33")]),
                        relancer=False)
    assert ligne(tableau, "Cible")["Dernière réponse"] in (None, "")


def test_mot_partage_pas_d_attribution(tableau, messagerie, faux_modele):
    """Deux entreprises « Atelier … » : un mail de atelier.jean@gmail.com n'est attribué à aucune."""
    ajouter(tableau, Entreprise="Atelier Numérique", Statut=C_FORMULAIRE)
    ajouter(tableau, Entreprise="Atelier Bois", Statut=C_FORMULAIRE)
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("atelier.jean@gmail.com")]), relancer=False)
    assert ligne(tableau, "Atelier Numérique")["Dernière réponse"] in (None, "")
    assert ligne(tableau, "Atelier Bois")["Dernière réponse"] in (None, "")



def test_preuves_avec_plusieurs_adresses():
    from rapprochement import preuves_dans_le_mail
    corps = "Cordialement, Léa — www.comptanova.com"
    assert preuves_dans_le_mail(corps, "Comptanova", "marc@gmail.com; rh@comptanova.com") == ["domaine comptanova.com"]
