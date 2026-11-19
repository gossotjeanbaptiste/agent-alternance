"""Rédaction et orientation des nouvelles candidatures (candidatures.py) ; lettres et réponses des
candidatures par formulaire (reponses.py). Le modèle, la messagerie et les sources sont simulés."""
import pytest

import candidatures
import commun
import reponses
from tableau import FORMULAIRE, LBA


# --- reponses.py ---------------------------------------------------------------------------------
class TestReponses:
    def test_enregistrer_fusionne(self):
        reponses.enregistrer("https://lien", {"motivations": "m"})
        reponses.enregistrer_lettre("https://lien", "Ma lettre")
        assert reponses.lire()["https://lien"] == {"motivations": "m", "lettre": "Ma lettre"}
        assert reponses.lettres() == {"https://lien": "Ma lettre"}

    def test_sans_lien_ou_mode_essai(self):
        reponses.enregistrer("", {"motivations": "m"})
        commun.ESSAI = True
        reponses.enregistrer("https://x", {"motivations": "m"})
        assert reponses.lire() == {}

    def test_fichier_illisible(self):
        reponses.FICHIER.write_text("{cassé", encoding="utf-8")
        assert reponses.lire() == {}

    @pytest.mark.parametrize("statut, poste, attendu", [
        (LBA, "Développeur web", True),
        (LBA, "Candidature spontanée", True),          # le site La Bonne Alternance les demande aussi
        (LBA, "", True), (LBA, None, True),
        ("À postuler (formulaire du site)", "Développeur web", False),
        ("Brouillon", "Développeur web", False),
    ])
    def test_questions_attendues(self, statut, poste, attendu):
        assert reponses.questions_attendues(statut, poste) is attendu

    def test_a_des_reponses(self):
        assert reponses.a_des_reponses({"motivations": "x"})
        assert not reponses.a_des_reponses({"lettre": "seulement la lettre"})
        assert not reponses.a_des_reponses({})
        assert not reponses.a_des_reponses(None)

    def test_en_liste_dans_l_ordre_du_formulaire(self):
        l = reponses.en_liste({"experiences": "E", "motivations": "M", "lettre": "L"})
        assert [t for t, _ in l] == [reponses.QUESTIONS[0][1], reponses.QUESTIONS[2][1]]
        assert [x for _, x in l] == ["M", "E"]

    def test_rediger_reponses(self, faux_modele, monkeypatch):
        import modele
        monkeypatch.setattr(modele, "llm_json", faux_modele.llm_json)
        faux_modele.reponses_json = [{"motivations": " M ", "missions": "Mi", "experiences": None, "autre": "x"}]
        r = reponses.rediger_reponses({"entreprise": "Exemple", "poste": "", "lieu": "Lyon"})
        assert r == {"motivations": "M", "missions": "Mi", "experiences": ""}
        p = faux_modele.consignes[0]
        assert "Exemple" in p and "candidature spontanée" in p
        for cle, _, consigne in reponses.QUESTIONS:
            assert f'"{cle}"' in p and consigne in p
        assert "600 à 900 caractères" in p
        assert p.index("INTERDIT") > p.index("Questions")       # contre-prompt à la fin


# --- rediger_candidature ---------------------------------------------------------------------------
class TestRedaction:
    def test_ton_formel_pour_une_adresse_generique(self, faux_modele):
        faux_modele.reponses_json = [{"objet": "Candidature", "corps": "Madame, Monsieur,"}]
        objet, corps = candidatures.rediger_candidature(
            {"entreprise": "Exemple", "email": "contact@exemple.fr", "contact": "Jean Dupont", "poste": "Dev"})
        assert (objet, corps) == ("Candidature", "Madame, Monsieur,")
        assert "formel, « Madame, Monsieur, »" in faux_modele.consignes[0]

    def test_ton_direct_pour_une_personne(self, faux_modele):
        faux_modele.reponses_json = [{"objet": "o", "corps": "c"}]
        candidatures.rediger_candidature({"entreprise": "E", "email": "jean.dupont@e.fr", "contact": "Jean Dupont"})
        assert "plus direct" in faux_modele.consignes[0]

    def test_profil_au_debut_interdits_a_la_fin(self, faux_modele):
        faux_modele.reponses_json = [{"objet": "o", "corps": "c"}]
        candidatures.rediger_candidature({"entreprise": "E"})
        p = faux_modele.consignes[0]
        assert p.startswith(commun.PROFIL)
        assert p.index("INTERDIT") > p.index("Écris un mail")


# --- nouvelles_candidatures : orientation ---------------------------------------------------------
@pytest.fixture
def scenario(monkeypatch, cfg, faux_modele):
    """Sources simulées, sites simulés, modèle simulé."""
    cfg["mails_par_jour"] = 10
    faux_modele.reponses_json = [{"objet": "Objet", "corps": "Madame, Monsieur,\n\nLettre.\n\nCordialement,"}] * 20

    class S:
        perso, linkedin, lba = [], [], []
        sites = {}        # nom -> {"site", "email", "formulaire"}

    monkeypatch.setattr(candidatures, "depuis_a_contacter", lambda suivi: S.perso)
    monkeypatch.setattr(candidatures, "depuis_linkedin", lambda ol: S.linkedin)
    monkeypatch.setattr(candidatures, "depuis_lba", lambda: iter(S.lba))
    monkeypatch.setattr(candidatures, "trouver_site", lambda nom, lieu="": S.sites.get(nom, {}).get("site", ""))
    monkeypatch.setattr(candidatures, "explorer_site",
                        lambda site, **k: next((dict(v) for v in S.sites.values() if v.get("site") == site),
                                          {"site": site, "email": "", "formulaire": ""}))
    monkeypatch.setattr(reponses, "rediger_reponses",
                        lambda o: {"motivations": "M", "missions": "Mi", "experiences": "E"})
    return S


def lba(nom, postulable=True, site="", siret=None):
    return {"entreprise": nom, "poste": "Candidature spontanée", "lieu": "Lyon", "contact": "", "email": "",
            "site": site, "siret": siret or str(abs(hash(nom)))[:14], "lien": f"https://labonnealternance.example/{nom}",
            "lba_postulable": postulable, "infos": "", "source": "La Bonne Alternance (Lyon)"}


def lignes(tableau):
    return {tableau.get(r, "Entreprise"): {c: tableau.get(r, c) for c in tableau.h} for r in tableau.rows()}


class TestOrientation:
    def test_adresse_trouvee_brouillon_de_mail(self, scenario, tableau, messagerie):
        scenario.lba = [lba("Avec Mail", site="https://avecmail.fr")]
        scenario.sites = {"Avec Mail": {"site": "https://avecmail.fr", "email": "contact@avecmail.fr", "formulaire": ""}}
        ol = messagerie()
        candidatures.nouvelles_candidatures(tableau, ol)
        l = lignes(tableau)["Avec Mail"]
        assert l["Statut"] == "Brouillon" and l["Email"] == "contact@avecmail.fr"
        assert ol.deposes[0]["a"] == "contact@avecmail.fr"
        assert "Site : https://avecmail.fr" in l["Notes"]

    def test_bouton_postuler_lba_sans_brouillon(self, scenario, tableau, messagerie):
        scenario.lba = [lba("Lba Ok")]
        ol = messagerie()
        candidatures.nouvelles_candidatures(tableau, ol)
        l = lignes(tableau)["Lba Ok"]
        assert l["Statut"] == LBA
        assert ol.deposes == []                                  # pas de brouillon de mail
        r = reponses.lire()["https://labonnealternance.example/Lba Ok"]
        assert r["lettre"].startswith("Madame, Monsieur,") and "Lien pour postuler" not in r["lettre"]
        assert r["motivations"] == "M"                           # candidature spontanée : réponses aussi

    def test_offre_lba_lettre_et_reponses(self, scenario, tableau, messagerie):
        o = lba("Offre Ok")
        o["poste"] = "Développeur web en alternance"
        scenario.lba = [o]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        r = reponses.lire()["https://labonnealternance.example/Offre Ok"]
        assert r["lettre"] and r["motivations"] == "M"

    def test_sans_bouton_mais_formulaire_du_site(self, scenario, tableau, messagerie):
        scenario.lba = [lba("Sans Bouton", postulable=False)]
        scenario.sites = {"Sans Bouton": {"site": "https://sansbouton.fr", "email": "",
                                          "formulaire": "https://sansbouton.fr/contact"}}
        ol = messagerie()
        candidatures.nouvelles_candidatures(tableau, ol)
        l = lignes(tableau)["Sans Bouton"]
        assert l["Statut"] == FORMULAIRE
        assert l["Lien"] == "https://sansbouton.fr/contact"
        assert "Fiche La Bonne Alternance (pas de bouton Postuler) : https://labonnealternance.example/Sans Bouton" in l["Notes"]
        assert ol.deposes == []
        r = reponses.lire()["https://sansbouton.fr/contact"]
        assert "lettre" in r and "motivations" not in r          # questions : seulement La Bonne Alternance

    def test_ni_adresse_ni_formulaire(self, scenario, tableau, messagerie):
        scenario.perso = [{"entreprise": "Inconnue", "poste": "", "lieu": "", "contact": "", "email": "",
                           "lien": "", "infos": "", "source": "Liste perso"}]
        ol = messagerie()
        candidatures.nouvelles_candidatures(tableau, ol)
        assert lignes(tableau)["Inconnue"]["Statut"] == "Brouillon (adresse à trouver)"
        # le nom de l'entreprise dans le champ « À » (adresse de remplacement, jamais distribuable)
        assert ol.deposes[0]["a"] == '"Inconnue (adresse à trouver)" <a-trouver@inconnue.invalid>'
        assert lignes(tableau)["Inconnue"]["Email"] in (None, "")          # pas notée comme vraie adresse

    def test_doublons_ignores(self, scenario, tableau, messagerie):
        tableau.add(**{"Entreprise": "Déjà Là", "Statut": "Refus"})
        scenario.lba = [lba("Déjà là"), lba("Nouvelle")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert set(lignes(tableau)) == {"Déjà Là", "Nouvelle"}

    def test_meme_entreprise_deux_fois_le_meme_jour(self, scenario, tableau, messagerie):
        scenario.lba = [lba("Double", siret="12345678900011"), lba("Double", siret="12345678900011")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert len(list(tableau.rows())) == 1

    def test_meme_domaine_qu_une_entreprise_deja_contactee(self, scenario, tableau, messagerie):
        tableau.add(**{"Entreprise": "Ancienne", "Email": "rh@groupe.fr"})
        scenario.lba = [lba("Filiale", site="https://groupe.fr")]
        scenario.sites = {"Filiale": {"site": "https://groupe.fr", "email": "contact@groupe.fr", "formulaire": ""}}
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert "Filiale" not in lignes(tableau)

    def test_nombre_par_jour_respecte(self, scenario, tableau, messagerie, cfg):
        cfg["mails_par_jour"] = 2
        scenario.lba = [lba(f"Boîte {i}") for i in range(6)]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert len(list(tableau.rows())) == 2

    def test_liste_perso_prioritaire(self, scenario, tableau, messagerie, cfg):
        cfg["mails_par_jour"] = 1
        scenario.perso = [{"entreprise": "Perso", "poste": "", "lieu": "", "contact": "", "email": "p@perso.fr",
                           "lien": "", "infos": "", "source": "Liste perso"}]
        scenario.lba = [lba("Lba")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert set(lignes(tableau)) == {"Perso"}

    def test_recherches_de_site_limitees(self, scenario, tableau, messagerie, cfg, monkeypatch):
        cfg["la_bonne_alternance"]["recherches_site_max"] = 1
        appels = []
        monkeypatch.setattr(candidatures, "trouver_site", lambda nom, lieu="": appels.append(nom) or "")
        scenario.lba = [lba("Un"), lba("Deux"), lba("Trois")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert len(appels) == 1

    def test_redaction_impossible_entreprise_sautee(self, scenario, tableau, messagerie, faux_modele):
        faux_modele.reponses_json = [RuntimeError("modèle indisponible")]
        scenario.lba = [lba("Echec")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert list(tableau.rows()) == []

    def test_aucune_entreprise(self, scenario, tableau, messagerie, capsys):
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert "Aucune nouvelle entreprise" in capsys.readouterr().out

    def test_ligne_a_contacter_marquee_traitee(self, scenario, tableau, messagerie):
        tableau.ac.append(["Perso", "", "", "", "p@perso.fr", "", "", None])
        import sources
        scenario.perso = sources.depuis_a_contacter(tableau)
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert str(tableau.ac.cell(2, 8).value).startswith("oui (")

    def test_mode_essai(self, scenario, tableau, messagerie):
        commun.ESSAI = True
        tableau.ac.append(["Perso", "", "", "", "p@perso.fr", "", "", None])
        import sources
        scenario.perso = sources.depuis_a_contacter(tableau)
        scenario.lba = [lba("Lba Essai")]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        assert tableau.ac.cell(2, 8).value is None              # rien marqué
        assert reponses.lire() == {}                             # rien enregistré


# --- pas d'invention sur l'entreprise ------------------------------------------------------------------
class TestPasDInvention:
    def test_regle_dans_les_deux_consignes(self, faux_modele, monkeypatch):
        """Lettre et réponses : secteur, produits… seulement d'après les infos données ; nom jamais commenté."""
        import modele
        monkeypatch.setattr(modele, "llm_json", faux_modele.llm_json)
        faux_modele.reponses_json = [{"objet": "o", "corps": "c"}, {"motivations": "m"}]
        candidatures.rediger_candidature({"entreprise": "Pixelo"})
        reponses.rediger_reponses({"entreprise": "Pixelo"})
        for p in faux_modele.consignes:
            assert reponses.NE_PAS_INVENTER in p and "Ne déduis RIEN de son nom" in p and "m'inspire" in p
            assert p.index("RÈGLE ABSOLUE") < p.index("INTERDIT")      # contre-prompt toujours à la fin
        assert "appuie-toi sur son nom et son secteur" not in faux_modele.consignes[1]

    @pytest.mark.parametrize("notes, attendu", [
        ("SIRET 12345678900011 | Activité : Edition de logiciels applicatifs | Site : https://pixelo.example",
         "Activité : Edition de logiciels applicatifs | Site : https://pixelo.example"),
        ("Relance 1 en brouillon | Formulaire : https://pixelo.example/contact", ""),
        (None, ""),
    ])
    def test_infos_du_tableau(self, notes, attendu):
        assert reponses.infos_du_tableau(notes) == attendu

    def test_activite_notee_au_tableau(self, scenario, tableau, messagerie):
        """L'activité officielle (code NAF de La Bonne Alternance) est gardée dans Notes pour les réécritures."""
        scenario.lba = [{**lba("Pixelo"), "activite": "Edition de logiciels applicatifs"}]
        candidatures.nouvelles_candidatures(tableau, messagerie())
        notes = [tableau.get(r, "Notes") for r in tableau.rows() if tableau.get(r, "Entreprise") == "Pixelo"][0]
        assert "Activité : Edition de logiciels applicatifs" in notes
