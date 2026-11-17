"""Mise à jour du suivi et relances (alternance/src/suivi.py). Messagerie et modèle simulés."""
from datetime import date, datetime, timedelta

import pytest

import suivi
from jours import date_relance
from tableau import MAIL, as_date


AUJ = date.today()


def ajouter(tableau, **v):
    v.setdefault("Entreprise", "Exemple")
    v.setdefault("Email", "jean@exemple.fr")
    tableau.add(**v)
    return list(tableau.rows())[-1]


def ligne(tableau, entreprise="Exemple"):
    r = next(r for r in tableau.rows() if tableau.get(r, "Entreprise") == entreprise)
    return {c: tableau.get(r, c) for c in tableau.h}


def recu(de, sujet="Re: candidature", corps="Bonjour", jours=0, classe="IPM.Note"):
    return {"de": de, "sujet": sujet, "corps": corps, "classe": classe,
            "date": datetime.combine(AUJ - timedelta(days=jours), datetime.min.time()).replace(hour=10)}


class Envoye:
    """Mail envoyé tel que le renvoie la messagerie (Body lu par texte_mail)."""
    def __init__(self, corps="Madame, Monsieur,\n\nJe vous écris…"):
        self.Body = corps


def envoi(jours, sujet="Candidature alternance", item=None):
    t = datetime.combine(AUJ - timedelta(days=jours), datetime.min.time()).replace(hour=9)
    return (t, sujet, item or Envoye())


# --- envois ---------------------------------------------------------------------------------------
class TestEnvois:
    def test_brouillon_envoye(self, tableau, messagerie):
        ajouter(tableau, Statut="Brouillon", **{"Date ajout": AUJ - timedelta(days=3)})
        suivi.mettre_a_jour(tableau, messagerie(envois={"jean@exemple.fr": [envoi(2)]}))
        l = ligne(tableau)
        assert l["Statut"] == MAIL
        assert as_date(l["Date envoi"]) == AUJ - timedelta(days=2)
        assert as_date(l["Relance prévue"]) == date_relance(AUJ - timedelta(days=2))

    def test_brouillon_pas_encore_envoye(self, tableau, messagerie):
        ajouter(tableau, Statut="Brouillon")
        suivi.mettre_a_jour(tableau, messagerie())
        assert ligne(tableau)["Statut"] == "Brouillon"

    def test_adresse_trouvee_apres_coup(self, tableau, messagerie):
        ajouter(tableau, Statut="Brouillon (adresse à trouver)")
        suivi.mettre_a_jour(tableau, messagerie(envois={"jean@exemple.fr": [envoi(1)]}))
        assert ligne(tableau)["Statut"] == MAIL

    def test_lignes_sans_adresse_ou_inactives_ignorees(self, tableau, messagerie):
        ajouter(tableau, Entreprise="Lba", Email="", Statut="À postuler (La Bonne Alternance)")
        ajouter(tableau, Entreprise="Fini", Statut="Refus")
        ajouter(tableau, Entreprise="Faux", Email="linkedin", Statut=MAIL)
        suivi.mettre_a_jour(tableau, messagerie(envois={"jean@exemple.fr": [envoi(1)]}))
        assert [ligne(tableau, e)["Statut"] for e in ("Lba", "Fini", "Faux")] == \
            ["À postuler (La Bonne Alternance)", "Refus", MAIL]

    def test_relance_envoyee(self, tableau, messagerie, cfg):
        cfg["relances_max"] = 2
        ajouter(tableau, Statut="Relance en brouillon", **{"Nb relances": 1, "Date envoi": AUJ - timedelta(days=12),
                                                           "Dernière action": AUJ - timedelta(days=3)})
        ol = messagerie(envois={"jean@exemple.fr": [envoi(12), envoi(1)]}, brouillons=[])
        suivi.mettre_a_jour(tableau, ol)
        l = ligne(tableau)
        assert l["Statut"] == "Relancé"
        assert as_date(l["Dernière action"]) == AUJ - timedelta(days=1)
        assert l["Relance prévue"] is not None

    def test_derniere_relance_envoyee_plus_de_relance_prevue(self, tableau, messagerie, cfg):
        cfg["relances_max"] = 2
        ajouter(tableau, Statut="Relance programmée", **{"Nb relances": 2, "Date envoi": AUJ - timedelta(days=20),
                                                         "Dernière action": AUJ - timedelta(days=5)})
        suivi.mettre_a_jour(tableau, messagerie(envois={"jean@exemple.fr": [envoi(20), envoi(1)]}))
        l = ligne(tableau)
        assert l["Statut"] == "Relancé" and l["Relance prévue"] is None


# --- relances programmées / supprimées --------------------------------------------------------------
class TestRelancesEnAttente:
    def base(self, tableau, statut="Relance en brouillon"):
        ajouter(tableau, Statut=statut, **{"Nb relances": 1, "Date envoi": AUJ - timedelta(days=10),
                                           "Dernière action": AUJ - timedelta(days=1)})

    def test_programmee(self, tableau, messagerie):
        self.base(tableau)
        suivi.mettre_a_jour(tableau, messagerie(programmes={"jean@exemple.fr": datetime(2026, 11, 20, 9, 31)},
                                                brouillons=["jean@exemple.fr"]))
        assert ligne(tableau)["Statut"] == "Relance programmée"

    def test_toujours_en_brouillon(self, tableau, messagerie):
        self.base(tableau)
        suivi.mettre_a_jour(tableau, messagerie(brouillons=["jean@exemple.fr"]))
        assert ligne(tableau)["Statut"] == "Relance en brouillon"

    def test_brouillon_supprime_relance_a_recreer(self, tableau, messagerie):
        self.base(tableau)
        suivi.mettre_a_jour(tableau, messagerie(brouillons=[]))
        l = ligne(tableau)
        assert l["Statut"] == MAIL and l["Nb relances"] == 0

    def test_messagerie_qui_ne_voit_pas_les_programmes(self, tableau, messagerie):
        self.base(tableau)
        ol = messagerie(brouillons=[])
        ol.voit_programmes = False
        suivi.mettre_a_jour(tableau, ol)
        assert ligne(tableau)["Statut"] == "Relance programmée"      # supposée programmée


# --- réponses et non-remises ----------------------------------------------------------------------
class TestReponses:
    def base(self, tableau, **v):
        ajouter(tableau, Statut=MAIL, **{"Date envoi": AUJ - timedelta(days=5), "Dernière action": AUJ - timedelta(days=5),
                                         "Relance prévue": AUJ + timedelta(days=5), **v})

    @pytest.mark.parametrize("typ, statut", [("entretien", "Entretien"), ("positive", "Réponse positive"),
                                             ("refus", "Refus"), ("transmise", "Candidature transmise"),
                                             ("autre", "Réponse à lire")])
    def test_reponse_classee(self, tableau, messagerie, faux_modele, typ, statut):
        self.base(tableau)
        faux_modele.reponses_json = [{"type": typ, "resume": "Résumé"}]
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("jean@exemple.fr", jours=1)]))
        l = ligne(tableau)
        assert l["Statut"] == statut and l["Relance prévue"] is None
        assert f"[{typ}] Résumé" in l["Dernière réponse"]

    def test_accuse_de_reception_automatique(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        faux_modele.reponses_json = [{"type": "automatique", "resume": "Accusé"}]
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("jean@exemple.fr", jours=1)]))
        l = ligne(tableau)
        assert l["Statut"] == MAIL and "[automatique]" in l["Dernière réponse"]

    def test_reponse_d_un_collegue_meme_domaine(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        faux_modele.reponses_json = [{"type": "refus", "resume": "Non"}]
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("rh@exemple.fr", jours=1)]))
        assert ligne(tableau)["Statut"] == "Refus"

    def test_domaine_de_l_ecole_ignore(self, tableau, messagerie, faux_modele):
        self.base(tableau, Email="prof@mon-ecole.fr")
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("secretariat@mon-ecole.fr", jours=1)]))
        assert ligne(tableau)["Statut"] == MAIL and faux_modele.consignes == []

    def test_domaine_partage_par_deux_lignes_adresse_exacte_seulement(self, tableau, messagerie, faux_modele):
        self.base(tableau, Entreprise="Labo A", Email="a@univ.fr")
        self.base(tableau, Entreprise="Labo B", Email="b@univ.fr")
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("c@univ.fr", jours=1)]))
        assert faux_modele.consignes == []

    def test_messagerie_grand_public_adresse_exacte_seulement(self, tableau, messagerie, faux_modele):
        self.base(tableau, Email="patron@gmail.com")
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("inconnu@gmail.com", jours=1)]))
        assert faux_modele.consignes == []

    def test_reponse_ancienne_ignoree(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("jean@exemple.fr", jours=30)]))
        assert faux_modele.consignes == []

    def test_reponse_deja_traitee_pas_reclassee(self, tableau, messagerie, faux_modele):
        r = recu("jean@exemple.fr", jours=1)
        self.base(tableau, **{"Dernière réponse": f"{r['date']:%Y-%m-%d %H:%M} [automatique] x"})
        suivi.mettre_a_jour(tableau, messagerie(recus=[r]))
        assert faux_modele.consignes == []

    def test_classement_impossible(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        faux_modele.reponses_json = [RuntimeError("modèle en panne")]
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("jean@exemple.fr", jours=1)]))
        l = ligne(tableau)
        assert l["Statut"] == "Réponse à lire" and "classement impossible" in l["Dernière réponse"]

    def test_classement_impossible_retente_au_passage_suivant(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        r = recu("jean@exemple.fr", jours=1)
        faux_modele.reponses_json = [RuntimeError("modèle en panne"), {"type": "transmise", "resume": "Transmis aux RH"}]
        suivi.mettre_a_jour(tableau, messagerie(recus=[r]))
        suivi.mettre_a_jour(tableau, messagerie(recus=[r]))
        l = ligne(tableau)
        assert l["Statut"] == "Candidature transmise" and "[transmise] Transmis aux RH" in l["Dernière réponse"]

    def test_transmise_reste_suivie_sans_relance(self, tableau, messagerie, faux_modele):
        # relance prévue dépassée : une candidature transmise ne doit pas être relancée
        self.base(tableau, **{"Relance prévue": AUJ - timedelta(days=1)})
        transfert = recu("jean@exemple.fr", jours=2)
        faux_modele.reponses_json = [{"type": "transmise", "resume": "Transmis aux RH"}]
        suivi.mettre_a_jour(tableau, messagerie(recus=[transfert]))
        assert ligne(tableau)["Statut"] == "Candidature transmise"
        # plus tard, les RH (même domaine) répondent : seule la nouvelle réponse est classée
        rh = recu("rh@exemple.fr", jours=1)
        faux_modele.reponses_json = [{"type": "entretien", "resume": "Entretien proposé"}]
        faux_modele.consignes.clear()
        suivi.mettre_a_jour(tableau, messagerie(recus=[transfert, rh]))
        l = ligne(tableau)
        assert l["Statut"] == "Entretien" and len(faux_modele.consignes) == 1

    def test_avis_de_non_remise(self, tableau, messagerie, faux_modele):
        self.base(tableau)
        ndr = recu("", sujet="Non remis : Candidature", corps="Adresse jean@exemple.fr introuvable",
                   jours=1, classe="REPORT.IPM.Note.NDR")
        suivi.mettre_a_jour(tableau, messagerie(recus=[ndr]))
        l = ligne(tableau)
        assert l["Statut"] == "Adresse invalide" and "non-remise" in l["Notes"]

    @pytest.mark.parametrize("sujet", ["Undeliverable: x", "Delivery has failed", "Échec de la remise"])
    def test_non_remise_reconnue_au_sujet(self, tableau, messagerie, sujet):
        self.base(tableau)
        suivi.mettre_a_jour(tableau, messagerie(recus=[recu("", sujet=sujet, corps="jean@exemple.fr", jours=1)]))
        assert ligne(tableau)["Statut"] == "Adresse invalide"


# --- relances ---------------------------------------------------------------------------------------
class TestRelances:
    def due(self, tableau, entreprise="Exemple", email="jean@exemple.fr", nb=0, statut=MAIL, contact=""):
        ajouter(tableau, Entreprise=entreprise, Email=email, Statut=statut, Contact=contact,
                **{"Nb relances": nb, "Date envoi": AUJ - timedelta(days=10), "Dernière action": AUJ - timedelta(days=10),
                   "Relance prévue": AUJ - timedelta(days=1)})

    def test_relance_due_en_brouillon(self, tableau, messagerie, faux_modele):
        self.due(tableau)
        orig = Envoye("Madame, Monsieur,\n\nMa candidature.\n\nCordialement,\nCamille Test\nÉtudiante\n" + "x" * 300)
        ol = messagerie(envois={"jean@exemple.fr": [envoi(10, "TR: Candidature alternance", orig)]},
                        brouillons=["jean@exemple.fr"])
        suivi.mettre_a_jour(tableau, ol)
        assert len(ol.deposes) == 1
        d = ol.deposes[0]
        assert d["a"] == "jean@exemple.fr" and d["base"] is orig and d["pieces"] == []
        assert d["sujet"] == "Relance : Candidature alternance"
        l = ligne(tableau)
        assert l["Statut"] == "Relance en brouillon" and l["Nb relances"] == 1 and "à planifier le" in l["Notes"]
        p = faux_modele.consignes[0]
        assert "RELANCE n°1" in p and "60 à 110 mots" in p and "Ma candidature." in p
        assert p.index("INTERDIT") > p.index("RELANCE")

    def test_routine_mails_recus_sans_relance(self, tableau, messagerie, faux_modele, capsys):
        """Routine « Mails reçus » : réponses et envois traités, mais aucun brouillon de relance écrit."""
        self.due(tableau, "Relance Due", "rh@due.fr")
        ajouter(tableau, Entreprise="Repond", Email="rh@repond.fr", Statut=MAIL,
                **{"Date envoi": AUJ - timedelta(days=5), "Dernière action": AUJ - timedelta(days=5),
                   "Relance prévue": AUJ + timedelta(days=5)})
        ajouter(tableau, Entreprise="Envoye", Email="rh@envoye.fr", Statut="Brouillon")
        faux_modele.reponses_json = [{"type": "entretien", "resume": "Entretien proposé"}]
        ol = messagerie(recus=[recu("rh@repond.fr", jours=1)], envois={"rh@envoye.fr": [envoi(2)]},
                        brouillons=["rh@due.fr"])
        suivi.mettre_a_jour(tableau, ol, relancer=False)
        assert ol.deposes == []                                             # aucune relance écrite
        assert ligne(tableau, "Repond")["Statut"] == "Entretien"           # réponse classée
        assert ligne(tableau, "Envoye")["Statut"] == MAIL                  # envoi repéré
        assert ligne(tableau, "Relance Due")["Statut"] == MAIL             # relance laissée pour plus tard
        assert "1 relance(s) due(s) : elles seront écrites par la routine « Relances »" in capsys.readouterr().out

    def test_relance_sans_mail_d_origine(self, tableau, messagerie, faux_modele, cfg, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        cfg["pieces_jointes"] = [str(cv)]
        self.due(tableau, contact="Jean Dupont")
        ol = messagerie(brouillons=["jean@exemple.fr"])
        suivi.mettre_a_jour(tableau, ol)
        d = ol.deposes[0]
        assert d["base"] is None and d["pieces"] == [str(cv)]
        assert d["sujet"] == "Relance : Candidature en alternance - Camille Test"
        assert "plus direct" in faux_modele.consignes[0]           # contact nommé

    def test_plafond_de_relances_par_jour(self, tableau, messagerie, faux_modele, cfg):
        cfg["relances_max_par_jour"] = 2
        for i in range(5):
            self.due(tableau, entreprise=f"E{i}", email=f"rh{i}@e{i}.fr")
        ol = messagerie(brouillons=[f"rh{i}@e{i}.fr" for i in range(5)])
        suivi.mettre_a_jour(tableau, ol)
        assert len(ol.deposes) == 2

    def test_relance_pas_encore_due(self, tableau, messagerie):
        ajouter(tableau, Statut=MAIL, **{"Date envoi": AUJ, "Relance prévue": AUJ + timedelta(days=10)})
        ol = messagerie()
        suivi.mettre_a_jour(tableau, ol)
        assert ol.deposes == []

    def test_max_atteint_sans_reponse(self, tableau, messagerie, cfg):
        cfg["relances_max"] = 2
        ajouter(tableau, Statut="Relancé", **{"Nb relances": 2, "Date envoi": AUJ - timedelta(days=40),
                                              "Dernière action": AUJ - timedelta(days=20)})
        ol = messagerie()
        suivi.mettre_a_jour(tableau, ol)
        assert ligne(tableau)["Statut"] == "Sans réponse" and ol.deposes == []

    def test_echec_de_redaction(self, tableau, messagerie, faux_modele, monkeypatch):
        self.due(tableau)

        def panne(*a, **k):
            raise RuntimeError("modèle en panne")
        monkeypatch.setattr(suivi, "llm", panne)
        ol = messagerie()
        suivi.mettre_a_jour(tableau, ol)
        assert ol.deposes == [] and ligne(tableau)["Statut"] == MAIL

    def test_longueur_de_relance_reglable(self, tableau, messagerie, faux_modele, cfg):
        cfg["redaction"] = {"longueur_relance": "3 phrases maximum"}
        self.due(tableau)
        suivi.mettre_a_jour(tableau, messagerie(brouillons=["jean@exemple.fr"]))
        assert "3 phrases maximum" in faux_modele.consignes[0]

    def test_gmail_conseil_de_programmation(self, tableau, messagerie, faux_modele, cfg, capsys):
        cfg["messagerie"]["type"] = "imap"
        self.due(tableau)
        suivi.mettre_a_jour(tableau, messagerie(brouillons=["jean@exemple.fr"]))
        assert "dans Gmail" in capsys.readouterr().out


def test_classer_reponse(faux_modele):
    faux_modele.reponses_json = [{"type": "entretien", "resume": "RDV mardi"}]
    assert suivi.classer_reponse("E", "Re", "corps") == ("entretien", "RDV mardi")
    faux_modele.reponses_json = [{}]
    assert suivi.classer_reponse("E", "Re", "corps") == ("autre", "")
    assert "corps" in faux_modele.consignes[0]
