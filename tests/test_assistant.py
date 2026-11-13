"""Assistant de premier lancement (web/src/assistant.py) et initialisation des données (donnees.initialiser).
Installation neuve simulée : config.json absent du dossier temporaire. Recherche des villes simulée."""
import io
import json
import shutil

import pytest

import agent
import assistant
import commun
import donnees
import emplacements


@pytest.fixture
def neuve(monkeypatch):
    """Installation neuve : pas de config.json (l'assistant doit s'afficher)."""
    emplacements.config_agent().unlink(missing_ok=True)
    yield
    emplacements.config_agent().unlink(missing_ok=True)


@pytest.fixture
def geo(monkeypatch):
    """geo.api.gouv.fr simulé : quelques villes connues."""
    connues = {"lyon": ("Lyon", 4.8357, 45.764), "villeurbanne": ("Villeurbanne", 4.8902, 45.7719)}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(url, timeout=None):
        import urllib.parse
        nom = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["nom"][0].lower()
        v = connues.get(nom)
        res = [{"nom": v[0], "centre": {"type": "Point", "coordinates": [v[1], v[2]]}, "population": 1}] if v else []
        return R(json.dumps(res).encode())
    monkeypatch.setattr(assistant.urllib.request, "urlopen", urlopen)


def config_agent():
    return json.loads(emplacements.config_agent().read_text(encoding="utf-8"))


# --- initialisation des données ---------------------------------------------------------------------
class TestInitialisation:
    def test_fichiers_crees_depuis_les_modeles(self, tmp_path):
        crees = donnees.initialiser(tmp_path / "neuf")
        assert sorted(crees) == ["config_alternance.json", "interdits.md", "profil.md"]
        cfg = json.loads((tmp_path / "neuf" / "config_alternance.json").read_text(encoding="utf-8"))
        assert cfg["tableau_suivi"] == "" and cfg["pieces_jointes"] == []

    def test_ne_remplace_jamais_un_fichier(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        (d / "profil.md").write_text("mon profil", encoding="utf-8")
        assert "profil.md" not in donnees.initialiser(d)
        assert (d / "profil.md").read_text(encoding="utf-8") == "mon profil"


# --- redirection -------------------------------------------------------------------------------------
class TestRedirection:
    def test_installation_neuve_assistant_d_abord(self, neuve, client):
        assert assistant.a_faire()
        r = client.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/assistant")
        assert client.get("/assistant").status_code == 200

    def test_actions_bloquees_pendant_l_assistant(self, neuve, client):
        r = client.post("/api/interdits", json={"texte": "x"})
        assert r.status_code == 409 and "assistant" in r.get_json()["message"]

    def test_deconnexion_possible_pendant_l_assistant(self, neuve, client):
        assert client.post("/api/deconnexion").status_code == 200

    def test_installation_configuree_pas_d_assistant(self, client):
        assert not assistant.a_faire()
        assert client.get("/").status_code == 200

    def test_ancienne_config_sans_marqueur(self, client):
        emplacements.config_agent().write_text(json.dumps({"serveurs": []}), encoding="utf-8")
        assert not assistant.a_faire()           # config existante (comme chez toi) : jamais d'assistant

    def test_page_assistant(self, neuve, client):
        h = client.get("/assistant").get_data(as_text=True)
        for etape in ("bienvenue", "tour", "messagerie", "lba", "profil", "cv", "fin"):
            assert f'data-etape="{etape}"' in h
        assert "Un deuxième PC pour l'IA" in h and "LM Studio" in h


# --- étapes ------------------------------------------------------------------------------------------
class TestEtapes:
    def test_sans_tour(self, neuve, client):
        r = client.post("/api/assistant/tour", json={"utiliser": False}).get_json()
        assert r["ok"]
        c = config_agent()
        assert c["utiliser_tour"] is False and c["serveurs"] == [{"nom": "ce PC", "url": "local"}]
        assert c["assistant_a_faire"] is True and not agent.utiliser_tour()

    def test_avec_tour(self, neuve, client):
        r = client.post("/api/assistant/tour", json={"utiliser": True, "url": "http://ma-tour:1236/v1/",
                                                     "mac": "AA:BB:CC:00:11:22", "ssh": "moi@ma-tour"}).get_json()
        assert r["ok"]
        c = config_agent()
        assert c["utiliser_tour"] is True and c["serveurs"][0] == {"nom": "tour", "url": "http://ma-tour:1236/v1",
                                                                   "reveil": True}
        assert c["serveurs"][-1]["url"] == "local" and c["tour"]["mac"] == "AA:BB:CC:00:11:22"

    def test_tour_sans_adresse_refusee(self, neuve, client):
        r = client.post("/api/assistant/tour", json={"utiliser": True, "url": "ma-tour"})
        assert r.status_code == 400

    def test_messagerie_outlook(self, neuve, client):
        assert client.post("/api/assistant/messagerie", json={"type": "outlook"}).get_json()["ok"]
        assert commun.CFG["messagerie"]["type"] == "outlook"

    def test_messagerie_gmail(self, neuve, client):
        r = client.post("/api/assistant/messagerie", json={"type": "imap", "adresse": "moi@gmail.com",
                                                           "mot_de_passe_app": "abcd efgh ijkl mnop"}).get_json()
        assert r["ok"]
        m = json.loads(commun.donnees.chemin("config_alternance.json").read_text(encoding="utf-8"))["messagerie"]
        assert m["type"] == "imap" and m["imap"]["adresse"] == "moi@gmail.com"
        assert m["imap"]["mot_de_passe_app"] == "abcd efgh ijkl mnop"

    @pytest.mark.parametrize("donnees_envoyees, message", [
        ({"type": "imap", "adresse": "pas-une-adresse", "mot_de_passe_app": "x"}, "adresse"),
        ({"type": "imap", "adresse": "moi@gmail.com"}, "mot de passe d'application"),
        ({"type": "pigeon"}, "inconnue"),
    ])
    def test_messagerie_refusee(self, neuve, client, donnees_envoyees, message):
        r = client.post("/api/assistant/messagerie", json=donnees_envoyees)
        assert r.status_code == 400 and message in r.get_json()["message"]

    def test_villes(self, neuve, client, geo):
        r = client.post("/api/assistant/lba", json={"villes": "lyon\n\nVilleurbanne", "rayon": "30", "jeton": "jeton-x"})
        assert r.get_json()["ok"]
        lba = commun.CFG["la_bonne_alternance"]
        assert [v["nom"] for v in lba["villes"]] == ["Lyon", "Villeurbanne"]
        assert lba["centre"]["nom"] == "Lyon" and lba["villes_prioritaires"] == ["Lyon"]
        assert lba["rayon_km"] == 30 and lba["jeton_api"] == "jeton-x"
        assert lba["villes"][0]["lat"] == pytest.approx(45.764)

    def test_ville_inconnue(self, neuve, client, geo):
        r = client.post("/api/assistant/lba", json={"villes": "Lyon\nAtlantide"})
        assert r.status_code == 400 and "Atlantide" in r.get_json()["message"]

    def test_sans_ville_ou_sans_reseau(self, neuve, client):
        assert client.post("/api/assistant/lba", json={"villes": ""}).status_code == 400
        r = client.post("/api/assistant/lba", json={"villes": "Ville-Absente-De-La-Config"})  # réseau bloqué
        assert r.status_code == 400 and "connexion" in r.get_json()["message"]

    def test_ville_connue_reprise_sans_reseau(self, neuve, client):
        """Une ville déjà dans la config (import) garde ses coordonnées, même introuvable par l'API."""
        assistant._ecrire_alternance({"la_bonne_alternance.villes": [{"nom": "Quartier-Ésotérique", "lat": 48.1, "lon": 7.2}]})
        r = client.post("/api/assistant/lba", json={"villes": "quartier esoterique"})   # réseau bloqué
        assert r.get_json()["ok"]
        assert commun.CFG["la_bonne_alternance"]["villes"] == [{"nom": "Quartier-Ésotérique", "lat": 48.1, "lon": 7.2}]

    def test_ville_saisie_a_la_main(self, neuve, client):
        r = client.post("/api/assistant/lba", json={"villes": "Lieu-dit ; 48,71834 ; 7.7043"})
        assert r.get_json()["ok"]
        assert commun.CFG["la_bonne_alternance"]["villes"] == [{"nom": "Lieu-dit", "lat": 48.7183, "lon": 7.7043}]

    @pytest.mark.parametrize("ligne", ["Nom ; abc ; 7", "Nom ; 95 ; 7", " ; 48 ; 7", "Nom ; 48"])
    def test_ville_saisie_invalide(self, ligne):
        assert assistant._ville_saisie(ligne) is None

    def test_message_ville_introuvable_explique_la_saisie(self, neuve, client, geo):
        m = client.post("/api/assistant/lba", json={"villes": "Atlantide"}).get_json()["message"]
        assert "latitude" in m

    def test_jeton_vide_garde_l_ancien(self, neuve, client, geo, cfg):
        client.post("/api/assistant/lba", json={"villes": "Lyon"})
        assert commun.CFG["la_bonne_alternance"]["jeton_api"] == "jeton-de-test"

    def test_profil(self, neuve, client):
        avant = commun.donnees.chemin("profil.md").read_text(encoding="utf-8")
        try:
            r = client.post("/api/assistant/profil", json={
                "profil": "Étudiant en informatique, je cherche une alternance de développeur web sur 2 ans.",
                "signature": {"nom": "Alex Test", "email": "alex@exemple.fr", "inconnu": "x"},
                "domaines": "Mon-Ecole.fr\n"}).get_json()
            assert r["ok"]
            assert commun.CFG["signature_formulaire"]["nom"] == "Alex Test"
            assert "inconnu" not in commun.CFG["signature_formulaire"]
            assert commun.CFG["debut_signature"] == "Alex Test" and commun.CFG["domaines_ignores"] == ["mon-ecole.fr"]
            assert "développeur web" in commun.donnees.chemin("profil.md").read_text(encoding="utf-8")
        finally:
            commun.donnees.chemin("profil.md").write_text(avant, encoding="utf-8")

    @pytest.mark.parametrize("d, message", [
        ({"profil": "trop court", "signature": {"nom": "A"}}, "trop court"),
        ({"profil": "x" * 60, "signature": {}}, "nom"),
    ])
    def test_profil_refuse(self, neuve, client, d, message):
        r = client.post("/api/assistant/profil", json=d)
        assert r.status_code == 400 and message in r.get_json()["message"]

    def test_cv(self, neuve, client):
        r = client.c.post("/api/assistant_cv", data={"fichier": (io.BytesIO(b"%PDF-1.4 cv"), "Mon CV (2026).pdf")},
                          headers={"Host": "127.0.0.1", "X-Jeton": __import__("securite").JETON},
                          content_type="multipart/form-data")
        assert r.get_json()["ok"]
        f = emplacements.dossier("pieces_jointes") / "Mon_CV_2026.pdf"
        assert f.read_bytes() == b"%PDF-1.4 cv"
        assert str(f) in commun.CFG["pieces_jointes"]
        f.unlink()

    @pytest.mark.parametrize("nom, contenu, message", [
        ("virus.exe", b"MZ", "Formats acceptés"),
        ("gros.pdf", b"x" * (assistant.TAILLE_CV_MAX + 1), "trop gros"),
    ], ids=["mauvais-format", "trop-gros"])
    def test_cv_refuse(self, neuve, client, nom, contenu, message):
        r = client.c.post("/api/assistant_cv", data={"fichier": (io.BytesIO(contenu), nom)},
                          headers={"Host": "127.0.0.1", "X-Jeton": __import__("securite").JETON},
                          content_type="multipart/form-data")
        assert r.status_code == 400 and message in r.get_json()["message"]

    def test_terminer(self, neuve, client):
        client.post("/api/assistant/tour", json={"utiliser": False})
        assert client.post("/api/assistant/terminer").get_json()["ok"]
        assert not assistant.a_faire()
        assert client.get("/").status_code == 200

    def test_etape_inconnue(self, neuve, client):
        assert client.post("/api/assistant/formatage", json={}).status_code == 404

    def test_config_neuve_sans_tour(self, neuve):
        c = assistant.config_agent()
        assert c["utiliser_tour"] is False and c["serveurs"] == [{"nom": "ce PC", "url": "local"}]
        assert c["assistant_a_faire"] is True and "modele" in c


# --- import d'une installation existante ------------------------------------------------------------
@pytest.fixture
def ancienne(tmp_path):
    """Copie du projet lancée depuis le code, avec ses données."""
    base = tmp_path / "lm_agent"
    d = base / "alternance" / "donnees"
    d.mkdir(parents=True)
    (d / "config_alternance.json").write_text(json.dumps({
        "tableau_suivi": str(d / "suivi_alternance.xlsx"), "pieces_jointes": [str(base / "pieces_jointes" / "cv.pdf"),
                                                                            "D:/ailleurs/autre.pdf"],
        "messagerie": {"type": "imap"}}), encoding="utf-8")
    (d / "profil.md").write_text("profil importé", encoding="utf-8")
    (d / "suivi_alternance.xlsx").write_bytes(b"xlsx")
    (d / "acces_interface.json").write_text("{}", encoding="utf-8")
    (base / "config.json").write_text(json.dumps({"utiliser_tour": True, "serveurs": [{"nom": "tour", "url": "http://t"}]}),
                                      encoding="utf-8")
    (base / "linkedin").mkdir()
    (base / "linkedin" / "Connections.csv").write_text("x", encoding="utf-8")
    (base / "pieces_jointes").mkdir()
    (base / "pieces_jointes" / "cv.pdf").write_bytes(b"%PDF")
    return base


class TestImport:
    @pytest.fixture(autouse=True)
    def sauvegarde(self):
        d = commun.donnees.DONNEES
        avant = {n: (d / n).read_bytes() for n in ("config_alternance.json", "profil.md", "interdits.md")}
        yield
        for n, b in avant.items():
            (d / n).write_bytes(b)
        (d / "suivi_alternance.xlsx").unlink(missing_ok=True)
        for sous in ("linkedin", "pieces_jointes"):
            shutil.rmtree(emplacements.dossier(sous), ignore_errors=True)

    def test_trouvee(self, ancienne):
        assert assistant.chercher_ancienne_installation(str(ancienne)) == ancienne
        assert assistant.chercher_ancienne_installation(str(ancienne.parent / "rien")) is None

    def test_import_complet(self, neuve, client, ancienne):
        r = client.post("/api/assistant/importer", json={"chemin": str(ancienne)}).get_json()
        assert r["ok"] and "config.json" in r["message"]
        d = commun.donnees.DONNEES
        assert (d / "profil.md").read_text(encoding="utf-8") == "profil importé"
        assert (d / "suivi_alternance.xlsx").read_bytes() == b"xlsx"
        assert (emplacements.dossier("linkedin") / "Connections.csv").exists()
        cfg = json.loads((d / "config_alternance.json").read_text(encoding="utf-8"))
        assert cfg["tableau_suivi"] == ""                                  # -> nouveau dossier de données
        assert cfg["pieces_jointes"] == [str(emplacements.dossier("pieces_jointes") / "cv.pdf"), "D:/ailleurs/autre.pdf"]
        c = config_agent()
        assert c["utiliser_tour"] is True and c["assistant_a_faire"] is False
        assert not assistant.a_faire()

    def test_compte_de_l_interface_non_importe(self, neuve, client, ancienne):
        import auth
        avant = auth.FICHIER.read_text(encoding="utf-8")
        client.post("/api/assistant/importer", json={"chemin": str(ancienne)})
        assert auth.FICHIER.read_text(encoding="utf-8") == avant

    def test_dossier_sans_installation(self, neuve, client, tmp_path):
        r = client.post("/api/assistant/importer", json={"chemin": str(tmp_path)})
        assert r.status_code == 400


class TestProfilDansParametres:
    def test_enregistrer(self, client):
        f = commun.donnees.chemin("profil.md")
        avant = f.read_text(encoding="utf-8")
        try:
            texte = "Étudiant en informatique.\r\nJe cherche une alternance de développeur web sur deux ans."
            r = client.post("/api/profil", json={"texte": texte}).get_json()
            assert r["ok"] and "\r" not in f.read_text(encoding="utf-8")
            assert "développeur web" in client.get("/parametres").get_data(as_text=True)
        finally:
            f.write_text(avant, encoding="utf-8")

    def test_refuse(self, client):
        assert client.post("/api/profil", json={"texte": "court"}).status_code == 400
        assert client.post("/api/profil", json={"texte": 3}).status_code == 400

    def test_lien_vers_l_assistant(self, client):
        h = client.get("/parametres").get_data(as_text=True)
        assert 'href="/assistant"' in h and 'id="pli-profil"' in h
