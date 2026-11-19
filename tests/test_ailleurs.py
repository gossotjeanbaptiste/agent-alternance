"""Candidatures faites en dehors de LM Agent (alternance/src/suivi/ailleurs.py) : accusés de réception et
réponses d'Indeed, HelloWork, LinkedIn, La Bonne Alternance ou d'un logiciel de recrutement. Messagerie et modèle
simulés ; formats repris de vrais mails, noms inventés."""
from datetime import date, datetime, timedelta

import suivi
from tableau import C_AUTRE, C_LBA, C_LINKEDIN, LBA, MAIL

AUJ = date.today()


def recu(de, sujet, corps="", jours=1):
    return {"de": de, "sujet": sujet, "corps": corps, "classe": "IPM.Note",
            "date": datetime.combine(AUJ - timedelta(days=jours), datetime.min.time()).replace(hour=11)}


def hellowork(entreprise, poste, jours=1):
    return recu("contact@emails.hellowork.com", f"Votre candidature est arrivée chez {entreprise}",
                f"Hello Camille !Votre candidature est enregistrée.\"{poste}\" pour l'entreprise {entreprise}. "
                ".Préparons la suite", jours)


def lignes(tableau):
    return [{c: tableau.get(r, c) for c in tableau.h} for r in tableau.rows()]


def ligne(tableau, entreprise):
    return next(l for l in lignes(tableau) if l["Entreprise"] == entreprise)


def test_accuse_hellowork_ajoute_la_candidature(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Développeur Full Stack H/F")]), relancer=False)
    l = ligne(tableau, "Vortalis")
    assert l["Poste"] == "Développeur Full Stack H/F" and l["Source"] == "HelloWork" and l["Statut"] == C_AUTRE
    assert l["Date envoi"] is not None and "[automatique]" in l["Dernière réponse"]
    assert faux_modele.consignes == []                     # format connu : pas besoin du modèle


def test_deuxieme_passage_rien_en_double(tableau, messagerie, faux_modele):
    ol = messagerie(recus=[hellowork("Vortalis", "Développeur Full Stack H/F")])
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    assert len(lignes(tableau)) == 1


def test_ligne_supprimee_pas_rajoutee(tableau, messagerie, faux_modele):
    ol = messagerie(recus=[hellowork("Vortalis", "Développeur Full Stack H/F")])
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    tableau.ws.delete_rows(2)                              # tu la supprimes à la main
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    assert lignes(tableau) == []


def test_indeed_poste_hors_informatique_ignore(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[
        recu("indeedapply@indeed.com", "Candidatures via Indeed : Serveur H/F | Brasserie du Port"),
        recu("indeedapply@indeed.com", "Candidatures via Indeed : Junior Cloud Developer (CDI) | Nuvola")]),
        relancer=False)
    assert [l["Entreprise"] for l in lignes(tableau)] == ["Nuvola"]
    assert ligne(tableau, "Nuvola")["Source"] == "Indeed"


def test_linkedin_candidature_envoyee(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[
        recu("jobs-noreply@linkedin.com", "Camille, votre candidature a été envoyée à Réseau Électrique Démo"),
        recu("jobs-noreply@linkedin.com", "Camille, déposez votre candidature maintenant pour ‘Stage chez Autre’")]),
        relancer=False)
    assert [(l["Entreprise"], l["Statut"]) for l in lignes(tableau)] == [("Réseau Électrique Démo", C_LINKEDIN)]


def test_hellowork_finalisez_n_est_pas_une_candidature(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[
        recu("contact@emails.hellowork.com", "Finalisez votre candidature sur le site de Vortalis")]), relancer=False)
    assert lignes(tableau) == [] and faux_modele.consignes == []


def test_la_bonne_alternance_a_postuler_devient_candidate(tableau, messagerie, faux_modele):
    tableau.add(Entreprise="Pixelmont", Statut=LBA)
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu(
        "nepasrepondre@apprentissage.beta.gouv.fr", "Votre candidature chez PIXELMONT",
        "Votre candidature spontanée a bien été envoyée à PIXELMONT [https://lba.example/x], 1 rue Démo 38000 "
        "GRENOBLE. J’envoie d’autres candidatures", jours=2)]), relancer=False)
    l = ligne(tableau, "Pixelmont")
    assert l["Statut"] == C_LBA and l["Date envoi"] == AUJ - timedelta(days=2)
    assert len(lignes(tableau)) == 1


def test_la_bonne_alternance_echec_adresse_invalide(tableau, messagerie, faux_modele):
    tableau.add(Entreprise="Pixelmont", Statut=LBA)
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu(
        "nepasrepondre@apprentissage.beta.gouv.fr", "Votre candidature n'a pas pu être envoyée à PIXELMONT")]),
        relancer=False)
    l = ligne(tableau, "Pixelmont")
    assert l["Statut"] == "Adresse invalide" and "pas pu envoyer" in l["Notes"]


def test_la_bonne_alternance_reponse_negative(tableau, messagerie, faux_modele):
    """« Réponse négative de <entreprise> à la candidature de <candidat> » : refus lu dans l'objet, sans le modèle,
    même si le texte cite le code postal de l'entreprise (pas de rattachement d'après le contenu)."""
    from tableau import C_LBA
    tableau.add(Entreprise="Pixelmont Software", Statut=C_LBA, Lieu="12 rue Démo 38000 Grenoble")
    tableau.add(Entreprise="Vortalis", Statut=C_LBA, Lieu="69003 Lyon")
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu(
        "nepasrepondre@apprentissage.beta.gouv.fr",
        "Réponse négative de PIXELMONT SOFTWARE à la candidature de Camille DUPONT",
        "Pixelmont Software, 12 rue Démo 38000 Grenoble, ne donne pas suite à votre candidature.")]), relancer=False)
    l = ligne(tableau, "Pixelmont Software")
    assert l["Statut"] == "Refus" and "[refus]" in l["Dernière réponse"] and "La Bonne Alternance" in l["Dernière réponse"]
    assert ligne(tableau, "Vortalis")["Statut"] == C_LBA and len(lignes(tableau)) == 2
    assert faux_modele.consignes == []                     # décision dans l'objet : pas besoin du modèle


def test_reponse_negative_entreprise_absente_ajoutee(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu(
        "nepasrepondre@apprentissage.beta.gouv.fr", "Réponse négative de NUVOLA à la candidature de Camille DUPONT")]),
        relancer=False)
    assert [(l["Entreprise"], l["Statut"], l["Source"]) for l in lignes(tableau)] == [("Nuvola", "Refus", "La Bonne Alternance")]


def test_reponse_d_un_logiciel_de_recrutement_lue_par_le_modele(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Développeur Java H/F", jours=5)]),
                        relancer=False)
    faux_modele.reponses_json = [{"candidature": True, "entreprise": "Vortalis", "poste": "Développeur Java",
                                  "type": "refus", "resume": "Pas de suite."}]
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu(
        "notification@ats.example", "Suite à votre candidature", "Nous ne donnerons pas suite…")]), relancer=False)
    l = ligne(tableau, "Vortalis")
    assert l["Statut"] == "Refus" and "[refus] Pas de suite." in l["Dernière réponse"] and len(lignes(tableau)) == 1


def test_mail_qui_n_est_pas_une_candidature(tableau, messagerie, faux_modele):
    faux_modele.reponses_json = [{"candidature": False}]
    ol = messagerie(recus=[recu("news@site.example", "Merci pour votre candidature à notre newsletter")])
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    assert lignes(tableau) == [] and len(faux_modele.consignes) == 1   # lu une seule fois


def test_modele_injoignable_mail_relu_plus_tard(tableau, messagerie, faux_modele):
    faux_modele.reponses_json = [RuntimeError("modèle éteint"),
                                 {"candidature": True, "entreprise": "Qubitec", "poste": "", "type": "automatique"}]
    ol = messagerie(recus=[recu("noreply@ats.example", "Accusé de réception de votre candidature")])
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    assert lignes(tableau) == []
    suivi.mettre_a_jour(tableau, ol, relancer=False)
    assert ligne(tableau, "Qubitec")["Source"] == "Site de l'entreprise"


def test_meme_entreprise_autre_poste_plus_tard_nouvelle_ligne(tableau, messagerie, faux_modele):
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Développeur Java H/F", jours=20)]),
                        relancer=False)
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Administrateur systèmes et réseaux", jours=1)]),
                        relancer=False)
    assert len(lignes(tableau)) == 2


def test_accuse_ancien_ne_change_pas_un_statut_plus_recent(tableau, messagerie, faux_modele):
    m = hellowork("Vortalis", "Développeur Java H/F", jours=3)
    tableau.add(Entreprise="Vortalis", Poste="Développeur Java H/F", Statut="Entretien",
                **{"Dernière réponse": f"{AUJ - timedelta(days=1):%Y-%m-%d} 09:00 [entretien] Entretien lundi"})
    suivi.mettre_a_jour(tableau, messagerie(recus=[m]), relancer=False)
    l = ligne(tableau, "Vortalis")
    assert l["Statut"] == "Entretien" and "[entretien]" in l["Dernière réponse"]


def test_mail_d_une_entreprise_suivie_laisse_au_rattachement(tableau, messagerie, faux_modele):
    tableau.add(Entreprise="Exemple", Email="jean@exemple.fr", Statut=MAIL,
                **{"Date envoi": AUJ - timedelta(days=5), "Relance prévue": AUJ + timedelta(days=5)})
    faux_modele.reponses_json = [{"type": "refus", "resume": "Non"}]
    suivi.mettre_a_jour(tableau, messagerie(recus=[recu("rh@exemple.fr", "Re: candidature")]), relancer=False)
    assert ligne(tableau, "Exemple")["Statut"] == "Refus" and len(faux_modele.consignes) == 1   # lu une seule fois


def test_reglage_desactive(tableau, messagerie, faux_modele, cfg):
    cfg["suivi_ailleurs"] = {"actif": False}
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Développeur Java H/F")]), relancer=False)
    assert lignes(tableau) == []


def test_mode_essai_ne_note_pas_les_mails_lus(tableau, messagerie, faux_modele):
    import commun
    import donnees
    commun.ESSAI = True
    suivi.mettre_a_jour(tableau, messagerie(recus=[hellowork("Vortalis", "Développeur Java H/F")]), relancer=False)
    assert not donnees.chemin("mails_candidatures.json").exists()
