"""Interface web (web/) : protection, pages, actions, données affichées, réglages.
La messagerie, les routines, les journaux et l'export LinkedIn sont simulés ou temporaires."""
import json
from datetime import date, timedelta

import pytest

import commun
import lettres
import parametres
import reglages
import reglages_web
import relations
import reponses
import routines
import securite
import suivi_donnees
from tableau import C_FORMULAIRE, C_LBA, FORMULAIRE, LBA, MAIL

AUJ = date.today()


@pytest.fixture(autouse=True)
def isolation(monkeypatch, tmp_path):
    """Pas d'Outlook, pas de vraie routine, journaux et export LinkedIn temporaires."""
    monkeypatch.setattr(lettres, "_outlook_ferme", lambda: True)
    monkeypatch.setitem(lettres.CACHE, "quand", 0)
    monkeypatch.setitem(routines.ROUTINE, "proc", None)
    import pages
    monkeypatch.setattr(pages, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(relations, "FICHIER", tmp_path / "Connections.csv")
    monkeypatch.setattr(routines, "LOGS", tmp_path / "logs")


def ajouter(tableau, **v):
    tableau.add(**v)
    tableau.save()


# --- protection ---------------------------------------------------------------------------------------
class TestSecurite:
    def test_hote_etranger_refuse(self, appli):
        assert appli.test_client().get("/", headers={"Host": "pirate.example:8765"}).status_code == 403

    @pytest.mark.parametrize("hote", ["127.0.0.1:8765", "localhost:8765", "localhost"])
    def test_hotes_locaux(self, appli, tableau, hote):
        # hôte accepté : redirigé vers la connexion (et non refusé)
        r = appli.test_client().get("/", headers={"Host": hote})
        assert r.status_code == 302 and r.headers["Location"].endswith("/connexion")

    def test_post_sans_jeton_refuse(self, client, tableau):
        assert client.post("/api/interdits", json={"texte": "x"}, jeton=False).status_code == 403

    def test_post_avec_mauvais_jeton(self, appli):
        r = appli.test_client().post("/api/interdits", json={"texte": "x"},
                                     headers={"Host": "127.0.0.1", "X-Jeton": "faux"})
        assert r.status_code == 403

    def test_post_depuis_un_autre_site(self, appli):
        r = appli.test_client().post("/api/interdits", json={"texte": "x"},
                                     headers={"Host": "127.0.0.1", "X-Jeton": securite.JETON,
                                              "Origin": "https://site-malveillant.example"})
        assert r.status_code == 403

    def test_jeton_aleatoire_et_dans_la_page(self, client, tableau):
        assert len(securite.JETON) >= 24
        assert securite.JETON in client.get("/").get_data(as_text=True)


# --- pages ------------------------------------------------------------------------------------------------
class TestPages:
    @pytest.mark.parametrize("url", ["/", "/suivi", "/postuler", "/routines", "/linkedin", "/journal", "/parametres"])
    def test_pages_affichees(self, client, tableau, url):
        r = client.get(url)
        assert r.status_code == 200
        h = r.get_data(as_text=True)
        assert "<title>LMAgent" in h and 'alt="LMAgent"' in h and "favicon.ico" in h

    @pytest.mark.parametrize("fichier", ["logo.png", "logo-wide.png", "favicon.ico", "style.css", "app.js"])
    def test_fichiers_statiques(self, client, fichier):
        r = client.get(f"/static/{fichier}")
        assert r.status_code == 200 and len(r.data) > 100

    def test_tableau_de_bord(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Statut": MAIL, "Date envoi": AUJ})
        ajouter(tableau, **{"Entreprise": "B", "Statut": LBA})
        h = client.get("/").get_data(as_text=True)
        assert "à postuler" in h

    def test_suivi_liste_les_entreprises(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "Visible SA", "Statut": "Refus"})
        assert "Visible SA" in client.get("/suivi").get_data(as_text=True)

    def test_journal_fichier_choisi_et_securite(self, client, tmp_path):
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "2026-11-13.log").write_text("ligne du journal", encoding="utf-8")
        assert "ligne du journal" in client.get("/journal").get_data(as_text=True)
        assert "ligne du journal" not in client.get("/journal?f=../../config.json").get_data(as_text=True)


# --- page À postuler ---------------------------------------------------------------------------------
class TestPostuler:
    def test_cartes_par_type(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "Lba Co", "Statut": LBA, "Lien": "https://lba/1", "Poste": "Développeur web",
                            "Notes": "Formulaire : https://lbaco.fr/contact"})
        ajouter(tableau, **{"Entreprise": "Form Co", "Statut": FORMULAIRE, "Lien": "https://formco.fr/contact"})
        ajouter(tableau, **{"Entreprise": "Mail Co", "Statut": "Brouillon", "Email": "rh@mailco.fr", "Lieu": "69003 Lyon"})
        ajouter(tableau, **{"Entreprise": "Hors Liste", "Statut": "Refus"})
        reponses.enregistrer("https://lba/1", {"lettre": "Lettre LBA", "motivations": "Parce que"})
        reponses.enregistrer_lettre("https://formco.fr/contact", "Lettre formulaire")
        h = client.get("/postuler").get_data(as_text=True)
        assert "Hors Liste" not in h
        assert h.index("Lba Co") < h.index("Mail Co") and h.index("Form Co") < h.index("Mail Co")   # mails à la fin
        assert "🎓 Formulaire La Bonne Alternance" in h and "📝 Formulaire de contact" in h and "📧" in h
        assert "Lettre LBA" in h and "Lettre formulaire" in h and "Parce que" in h
        assert "Camille Test" in h                                     # signature sous les lettres
        assert "https://lbaco.fr/contact" in h                         # 2e solution : formulaire du site
        assert "https://www.google.com/search?q=Mail+Co+Lyon" in h
        assert "https://mailco.fr" in h                                # site d'après l'adresse
        assert "Outlook classique fermé" in h
        assert f"'{C_LBA}'" in h and f"'{C_FORMULAIRE}'" in h and f"'{MAIL}'" in h
        assert "Accepter" not in h

    def test_reponses_manquantes_signalees(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "Lba Co", "Statut": LBA, "Lien": "https://lba/1", "Poste": "Développeur web"})
        reponses.enregistrer_lettre("https://lba/1", "Lettre")
        assert "pas encore écrites" in client.get("/postuler").get_data(as_text=True)

    def test_candidature_spontanee_lettre_seulement(self, client, tableau):
        """Pas d'offre sur la page de l'entreprise : ni réponses affichées (même anciennes), ni rappel de les écrire."""
        ajouter(tableau, **{"Entreprise": "Spontanée Co", "Statut": LBA, "Lien": "https://lba/2",
                            "Poste": "Candidature spontanée"})
        reponses.enregistrer("https://lba/2", {"lettre": "Lettre spontanée", "motivations": "Ancienne réponse"})
        h = client.get("/postuler").get_data(as_text=True)
        assert "Lettre spontanée" in h
        assert "Ancienne réponse" not in h and "pas encore écrites" not in h and "Copier la réponse" not in h

    def test_adresse_a_trouver_affichee(self, client, tableau, monkeypatch):
        import postuler
        ajouter(tableau, **{"Entreprise": "Mail Co", "Statut": "Brouillon", "Email": "rh@mailco.fr"})
        ajouter(tableau, **{"Entreprise": "Sans Adresse", "Statut": "Brouillon (adresse à trouver)",
                            "Lieu": "12 rue X 69003 Lyon", "Notes": "Site : https://sansadresse.fr"})
        ajouter(tableau, **{"Entreprise": "Introuvable", "Statut": "Brouillon (adresse à trouver)"})
        monkeypatch.setattr(lettres, "_outlook_ferme", lambda: False)
        monkeypatch.setattr(lettres, "lettres_et_signature", lambda: ({
            "rh@mailco.fr": "Lettre du mail",
            postuler.SANS_DESTINATAIRE: [("Candidature spontanée chez Sans Adresse", "Madame, Monsieur, lettre sans adresse")],
        }, "Camille Test"))
        lettres.CACHE["note"] = None
        h = client.get("/postuler").get_data(as_text=True)
        assert h.count("📭 <b>Adresse à trouver</b>") == 2
        assert h.index("Mail Co") < h.index("Sans Adresse")                     # après les mails
        assert "lettre sans adresse" in h and "Chercher l'adresse de contact" in h
        assert "q=Sans+Adresse+Lyon+contact+recrutement+email" in h and "https://sansadresse.fr" in h
        assert "envoyeeSansAdresse(" in h and 'data-type="3"' in h
        assert "aucun brouillon sans destinataire ne parle de Introuvable" in h

    def test_lettre_sans_destinataire(self):
        brouillons = [("Candidature alternance", "Bonjour, je souhaite rejoindre XEFI SAS à Lyon"),
                      ("Candidature chez Autre", "...")]
        assert lettres.lettre_sans_destinataire("Xefi", brouillons).startswith("Bonjour")
        assert lettres.lettre_sans_destinataire("Autre", brouillons) == "..."
        assert lettres.lettre_sans_destinataire("Inconnue", brouillons) is None
        assert lettres.lettre_sans_destinataire("AB", brouillons) is None          # nom trop court : pas de devinette

    def test_site_ou_recherche(self):
        assert lettres.site_ou_recherche({"Notes": "SIRET 1 | Site : https://a.fr | x", "Entreprise": "A"})[0] == "https://a.fr"
        assert lettres.site_ou_recherche({"Email": "rh@boite.fr", "Entreprise": "B"})[0] == "https://boite.fr"
        assert lettres.site_ou_recherche({"Email": "boite@gmail.com", "Entreprise": "C"})[0] == ""
        assert lettres.site_ou_recherche({"Email": "x@0.0.1", "Entreprise": "D"})[0] == ""
        _, g = lettres.site_ou_recherche({"Entreprise": "Ma Boîte", "Lieu": "12 rue X 69003 Lyon"})
        assert g == "https://www.google.com/search?q=Ma+Bo%C3%AEte+Lyon"


# --- actions -----------------------------------------------------------------------------------------------
class TestActions:
    def ligne(self, tableau, entreprise):
        from tableau import Suivi
        s = Suivi(tableau.path)
        r = next(r for r in s.rows() if s.get(r, "Entreprise") == entreprise)
        return r[0].row, {c: s.get(r, c) for c in s.h}

    def test_statut_envoyee_par_mail(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon", "Email": "rh@a.fr"})
        n, _ = self.ligne(tableau, "A")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": MAIL, "postule": True})
        assert r.get_json()["ok"]
        _, l = self.ligne(tableau, "A")
        assert l["Statut"] == MAIL and l["Date envoi"].date() == AUJ and l["Relance prévue"] is not None

    def test_envoyee_adresse_trouvee_notee(self, client, tableau):
        """Adresse à trouver : l'adresse saisie à « Envoyée » est notée (suivi des réponses, relance)."""
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon (adresse à trouver)"})
        n, _ = self.ligne(tableau, "A")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": MAIL, "postule": True,
                                             "email": " rh@a.fr "})
        assert r.get_json()["ok"]
        _, l = self.ligne(tableau, "A")
        assert l["Statut"] == MAIL and l["Email"] == "rh@a.fr" and l["Relance prévue"] is not None

    def test_envoyee_sans_adresse(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon (adresse à trouver)"})
        n, _ = self.ligne(tableau, "A")
        assert client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": MAIL, "postule": True,
                                                "email": ""}).get_json()["ok"]
        assert self.ligne(tableau, "A")[1]["Statut"] == MAIL

    def test_adresse_invalide_refusee(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon (adresse à trouver)"})
        n, _ = self.ligne(tableau, "A")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": MAIL, "postule": True,
                                             "email": "pas une adresse"})
        assert r.status_code == 400 and "invalide" in r.get_json()["message"]
        assert self.ligne(tableau, "A")[1]["Statut"] == "Brouillon (adresse à trouver)"   # rien de changé

    def test_statut_formulaire_sans_relance(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "B", "Statut": FORMULAIRE})
        n, _ = self.ligne(tableau, "B")
        client.post("/api/statut", json={"ligne": n, "entreprise": "B", "statut": C_FORMULAIRE, "postule": True})
        _, l = self.ligne(tableau, "B")
        assert l["Statut"] == C_FORMULAIRE and l["Date envoi"].date() == AUJ and l["Relance prévue"] is None

    def test_statut_inconnu(self, client, tableau):
        r = client.post("/api/statut", json={"ligne": 2, "entreprise": "A", "statut": "N'importe quoi"})
        assert r.status_code == 400

    def test_mauvaise_ligne_refusee(self, client, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon"})
        n, _ = self.ligne(tableau, "A")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "Autre", "statut": "Refus"}).get_json()
        assert not r["ok"] and "recharge" in r["message"]

    def test_abandon_par_mail_met_le_brouillon_a_la_corbeille(self, client, tableau, monkeypatch):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon", "Email": "rh@a.fr"})
        n, _ = self.ligne(tableau, "A")
        appels = []
        monkeypatch.setattr(lettres, "supprimer_brouillons", lambda a: appels.append(a) or "Brouillon mis à la corbeille.")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": "Abandonné",
                                             "brouillon_a": "rh@a.fr"}).get_json()
        assert r["ok"] and "corbeille" in r["message"] and appels == ["rh@a.fr"]
        assert self.ligne(tableau, "A")[1]["Statut"] == "Abandonné"

    def test_modification_refusee_pendant_une_routine(self, client, tableau, monkeypatch):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon"})
        monkeypatch.setattr(routines, "en_cours", lambda: True)
        n, _ = self.ligne(tableau, "A")
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": "Refus"}).get_json()
        assert not r["ok"] and "routine" in r["message"]

    def test_tableau_ouvert_dans_excel(self, client, tableau, monkeypatch):
        ajouter(tableau, **{"Entreprise": "A", "Statut": "Brouillon"})
        n, _ = self.ligne(tableau, "A")
        import openpyxl.workbook.workbook as wbmod
        monkeypatch.setattr(wbmod.Workbook, "save", lambda self, f: (_ for _ in ()).throw(PermissionError()))
        r = client.post("/api/statut", json={"ligne": n, "entreprise": "A", "statut": "Refus"}).get_json()
        assert not r["ok"] and "Excel" in r["message"]

    def test_lancer_une_routine(self, client, monkeypatch, tmp_path):
        lances = []

        class Proc:
            returncode = 0

            def poll(self):
                return None
        monkeypatch.setattr(routines.subprocess, "Popen", lambda cmd, **k: lances.append(cmd) or Proc())
        assert client.post("/api/routine/recherche", json={"essai": True, "fois": 3}).get_json()["ok"]
        cmd = lances[0]
        assert cmd[-5:] == ["--routine", "recherche", "--fois", "3", "--essai"]
        assert cmd[1].endswith("lmagent.py")                       # depuis le code : python lmagent.py
        assert "×3" in routines.ROUTINE["nom"] and "(essai)" in routines.ROUTINE["nom"]
        assert routines.ROUTINE["fichier"].name.endswith("_recherche_x3_essai.txt")
        r = client.post("/api/routine/relances", json={})
        assert r.status_code == 409                                 # une routine tourne déjà

    def test_passages_plafonnes(self, client, monkeypatch, cfg):
        cfg["interface"] = {"passages_max": 5}
        lances = []
        monkeypatch.setattr(routines.subprocess, "Popen",
                            lambda cmd, **k: lances.append(cmd) or type("P", (), {"poll": lambda s: 0, "returncode": 0})())
        client.post("/api/routine/relances", json={"fois": 999})
        assert lances[0][-2:] == ["--fois", "5"]

    def test_routine_inconnue(self, client):
        assert client.post("/api/routine/formatage", json={}).status_code == 404

    def test_historique(self, client, tmp_path):
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "web_20261113_relances.txt").write_text("a\nb\nfin", encoding="utf-8")
        assert client.get("/api/historique/web_20261113_relances.txt").get_json()["sortie"].endswith("fin")
        assert client.get("/api/historique/..%2F..%2Fconfig.json").status_code == 404
        assert client.get("/api/historique/2026-11-13.log").status_code == 404     # préfixe web_ exigé


# --- paramètres ---------------------------------------------------------------------------------------------
class TestParametres:
    def test_signature(self, client):
        sig = {"nom": "Nouveau Nom", "titre": "T", "telephone": "", "email": "", "linkedin": "", "portfolio": "", "github": ""}
        r = client.post("/api/signature", json={"signature": sig, "debut": "Nouveau Nom", "ajouter": True}).get_json()
        assert r["ok"]
        assert commun.CFG["signature_formulaire"]["nom"] == "Nouveau Nom" and commun.CFG["ajouter_signature"] is True
        enregistre = json.loads(parametres.FICHIER.read_text(encoding="utf-8"))
        assert enregistre["signature_formulaire"]["nom"] == "Nouveau Nom"
        parametres.FICHIER.write_text(json.dumps(_config_origine(), ensure_ascii=False), encoding="utf-8")

    def test_signature_invalide(self, client):
        assert client.post("/api/signature", json={"signature": "pas un dict"}).status_code == 400

    def test_interdits(self, client):
        avant = commun.INTERDITS.read_text(encoding="utf-8")
        try:
            r = client.post("/api/interdits", json={"texte": "# titre\r\n- règle 1\r\n- règle 2"}).get_json()
            assert r["ok"] and "2 interdiction(s)" in r["message"]
            assert "\r" not in commun.INTERDITS.read_text(encoding="utf-8")
            assert client.post("/api/interdits", json={"texte": 3}).status_code == 400
        finally:
            commun.INTERDITS.write_text(avant, encoding="utf-8")

    def test_page_sans_secret_affiche(self, client, cfg):
        h = client.get("/parametres").get_data(as_text=True)
        assert "jeton-de-test" not in h
        assert "Tous les réglages" in h and h.count('class="carte pli-section"') >= 10


class TestReglagesWeb:
    @pytest.fixture(autouse=True)
    def fichiers_temporaires(self, monkeypatch, tmp_path):
        alt = tmp_path / "config_alternance.json"
        alt.write_text(json.dumps(_config_origine(), ensure_ascii=False), encoding="utf-8")
        agent = tmp_path / "config.json"
        agent.write_text(json.dumps({"modele": "m", "tour": {"ssh": "u@t"}, "serveurs": []}), encoding="utf-8")
        monkeypatch.setattr(reglages_web, "FICHIERS", {"alternance": lambda: alt, "agent": lambda: agent})
        self.alt, self.agent = alt, agent

    def valeurs_affichees(self):
        v = {}
        for _, champs in reglages_web.sections():
            for c in champs:
                v[c["cle"]] = c["valeur"]
        return v

    def test_enregistrer_tel_quel_ne_change_rien(self):
        avant = (self.alt.read_text(encoding="utf-8"), self.agent.read_text(encoding="utf-8"))
        ok, msg = reglages_web.enregistrer(self.valeurs_affichees())
        assert ok and msg == "Aucun changement."
        assert (self.alt.read_text(encoding="utf-8"), self.agent.read_text(encoding="utf-8")) == avant

    def test_modification_et_nouveau_reglage(self):
        v = self.valeurs_affichees()
        v["alternance|mails_par_jour"] = "9"
        v["alternance|sites.annuaires"] = "societe.com\n  pappers \n\n"
        v["alternance|la_bonne_alternance.poids_min"] = "0,2"
        v["agent|modele"] = "autre/modele"
        ok, msg = reglages_web.enregistrer(v)
        assert ok and "4 réglage(s)" in msg
        a = json.loads(self.alt.read_text(encoding="utf-8"))
        assert a["mails_par_jour"] == 9 and a["sites"]["annuaires"] == ["societe.com", "pappers"]
        assert a["la_bonne_alternance"]["poids_min"] == 0.2
        assert json.loads(self.agent.read_text(encoding="utf-8"))["modele"] == "autre/modele"
        assert commun.CFG["mails_par_jour"] == 9                  # copie en mémoire mise à jour

    def test_secret_vide_garde_la_valeur(self):
        v = self.valeurs_affichees()
        assert v["alternance|la_bonne_alternance.jeton_api"] == ""      # jamais affiché
        reglages_web.enregistrer(v)
        assert json.loads(self.alt.read_text(encoding="utf-8"))["la_bonne_alternance"]["jeton_api"] == "jeton-de-test"
        v["alternance|la_bonne_alternance.jeton_api"] = "nouveau"
        reglages_web.enregistrer(v)
        assert json.loads(self.alt.read_text(encoding="utf-8"))["la_bonne_alternance"]["jeton_api"] == "nouveau"

    @pytest.mark.parametrize("cle, valeur, message", [
        ("alternance|mails_par_jour", "beaucoup", "nombre entier attendu"),
        ("alternance|la_bonne_alternance.poids_min", "un peu", "nombre attendu"),
        ("alternance|la_bonne_alternance.villes", "[{cassé", "format JSON invalide"),
        ("alternance|messagerie.type", "pigeon", "choisir parmi"),
        ("agent|tour.wol_internet.ports", "neuf", "nombres entiers"),
    ])
    def test_valeur_invalide_rien_n_est_ecrit(self, cle, valeur, message):
        avant = self.alt.read_text(encoding="utf-8")
        v = self.valeurs_affichees()
        v[cle] = valeur
        ok, msg = reglages_web.enregistrer(v)
        assert not ok and message in msg and "Rien n'est enregistré" in msg
        assert self.alt.read_text(encoding="utf-8") == avant

    def test_cases_a_cocher(self):
        v = self.valeurs_affichees()
        v["alternance|jours_feries_alsace"] = True
        reglages_web.enregistrer(v)
        assert json.loads(self.alt.read_text(encoding="utf-8"))["jours_feries_alsace"] is True

    def test_cle_inconnue_ignoree(self):
        ok, msg = reglages_web.enregistrer({"alternance|pirate": "x", "nimporte": "y"})
        assert ok and msg == "Aucun changement."

    def test_api(self, client):
        r = client.post("/api/reglages", json={"valeurs": {"alternance|mails_par_jour": "4"}}).get_json()
        assert r["ok"] and json.loads(self.alt.read_text(encoding="utf-8"))["mails_par_jour"] == 4
        assert client.post("/api/reglages", json={"valeurs": "x"}).status_code == 400

    def test_section_tour_seulement_si_une_tour_est_utilisee(self):
        from chemins import ROOT
        titres = [t for t, _ in reglages_web.sections()]
        assert "Tour" not in titres                         # config sans serveur distant : pas de tour
        self.agent.write_text(json.dumps({"utiliser_tour": True}), encoding="utf-8")
        titres = [t for t, _ in reglages_web.sections()]
        assert ("Tour" in titres) == (ROOT / "src" / "tour.py").exists()

    def test_case_utiliser_tour_deduite_des_serveurs(self):
        self.agent.write_text(json.dumps({"serveurs": [{"nom": "tour", "url": "http://t:1236/v1"}]}), encoding="utf-8")
        assert self.valeurs_affichees()["agent|utiliser_tour"] is True
        self.agent.write_text(json.dumps({"serveurs": [{"nom": "ce PC", "url": "local"}]}), encoding="utf-8")
        assert self.valeurs_affichees()["agent|utiliser_tour"] is False


# --- données du tableau de bord et relations LinkedIn ----------------------------------------------------
class TestDonnees:
    def test_statistiques(self):
        lignes = [
            {"Statut": MAIL, "Date envoi": AUJ - timedelta(days=1), "Relance prévue": AUJ + timedelta(days=3)},
            {"Statut": "Refus", "Date envoi": AUJ - timedelta(days=20)},
            {"Statut": "Entretien", "Date envoi": AUJ - timedelta(days=2)},
            {"Statut": LBA}, {"Statut": FORMULAIRE},
            {"Statut": "Relancé", "Date envoi": AUJ - timedelta(days=15), "Relance prévue": AUJ + timedelta(days=1)},
        ]
        s = suivi_donnees.statistiques(lignes)
        assert s["envoyees"] == 4 and s["reponses"] == 2 and s["taux"] == 50
        assert s["entretiens"] == 1 and s["a_postuler"] == 2 and s["semaine"] == 2
        assert [l["Statut"] for l in s["relances"]] == ["Relancé", MAIL]       # triées par date
        assert len(s["semaines"]) == 10 and s["maxi"] >= 1

    def test_a_postuler_compte_comme_la_page(self, client, tableau):
        """Le chiffre du tableau de bord = le nombre de cartes de la page « À postuler »."""
        for nom, statut in (("Lba", LBA), ("Form", FORMULAIRE), ("Mail", "Brouillon"),
                            ("Sans", "Brouillon (adresse à trouver)"), ("Fini", MAIL), ("Non", "Refus")):
            ajouter(tableau, **{"Entreprise": nom, "Statut": statut, "Email": "rh@mail.fr" if nom == "Mail" else ""})
        assert suivi_donnees.statistiques(suivi_donnees.lire())["a_postuler"] == 4
        h = client.get("/").get_data(as_text=True)
        assert '<a href="/postuler">4</a>' in h and "mails à envoyer, adresses à trouver" in h
        page = client.get("/postuler").get_data(as_text=True)
        assert page.count('class="carte" id="c') == 4

    def test_statistiques_tableau_vide(self):
        s = suivi_donnees.statistiques([])
        assert s["envoyees"] == 0 and s["taux"] == 0 and s["maxi"] == 1

    def test_lire_convertit_les_dates(self, tableau):
        ajouter(tableau, **{"Entreprise": "A", "Date envoi": AUJ})
        l = suivi_donnees.lire()[0]
        assert l["Date envoi"] == AUJ and l["_ligne"] == 2

    def test_relations_linkedin(self, tmp_path, client, tableau):
        relations.FICHIER.write_text(
            "Notes:\n\"texte\"\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
            "Jean,Dupont,https://linkedin.com/in/jd,,Exemple Informatique SAS,Dev,10 Nov 2026\n"
            "Paul,Martin,https://linkedin.com/in/pm,,Autre,RH,10 Nov 2026\n", encoding="utf-8")
        rel = relations.lire_relations()
        assert len(rel) == 2
        t = relations.correspondances([{"Entreprise": "Exemple Informatique", "Statut": MAIL}], rel)
        assert [x["nom"] for x in t] == ["Jean Dupont"] and t[0]["statut"] == MAIL
        ajouter(tableau, **{"Entreprise": "Exemple Informatique", "Statut": MAIL})
        assert "Jean Dupont" in client.get("/linkedin").get_data(as_text=True)

    def test_relations_sans_fichier(self):
        assert relations.lire_relations() is None

    def test_noms_trop_courts_non_rapproches(self):
        rel = [{"Company": "AB", "First Name": "x", "Last Name": "y"}]
        assert relations.correspondances([{"Entreprise": "AB"}], rel) == []


class TestRoutines:
    def test_fichier_du_journal_refuse_les_chemins_douteux(self, tmp_path):
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "web_a.txt").write_text("x", encoding="utf-8")
        assert routines.fichier_du_journal("web_a.txt", "web_") == logs / "web_a.txt"
        assert routines.fichier_du_journal("../secret.txt") is None
        assert routines.fichier_du_journal("absent.txt") is None
        assert routines.fichier_du_journal("web_a.txt", "autre_") is None

    def test_fin_de_fichier(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("\n".join(str(i) for i in range(500)), encoding="utf-8")
        assert routines.fin_de_fichier(f, 3) == "497\n498\n499"
        assert routines.fin_de_fichier(tmp_path / "absent") == ""

    def test_etat_sans_routine(self):
        e = routines.etat()
        assert e["en_cours"] is False and e["code"] is None


def _config_origine():
    import conftest
    return conftest.CFG_ORIGINE
