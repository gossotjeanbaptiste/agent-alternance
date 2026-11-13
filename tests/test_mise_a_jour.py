"""Mises à jour automatiques (mise_a_jour.py) : GitHub et téléchargements simulés, rien n'est installé."""
import hashlib
import io
import json

import pytest

import emplacements
import mise_a_jour


@pytest.mark.parametrize("v, attendu", [
    ("v1.2.3", (1, 2, 3)), ("1.10.0", (1, 10, 0)), ("v2", (2,)), (" v0.9.1-beta ", (0, 9, 1)),
    ("n'importe quoi", (0,)), (None, (0,)),
])
def test_numero(v, attendu):
    assert mise_a_jour.numero(v) == attendu


@pytest.mark.parametrize("distante, locale, attendu", [
    ("v1.0.1", "1.0.0", True), ("v1.10.0", "1.9.9", True), ("v2.0", "1.99.99", True),
    ("v1.0.0", "1.0.0", False), ("v0.9.0", "1.0.0", False), ("pas une version", "1.0.0", False),
])
def test_plus_recente(distante, locale, attendu):
    assert mise_a_jour.plus_recente(distante, locale) is attendu


@pytest.mark.parametrize("texte, attendu", [
    ("a" * 64 + "  LMAgent-1.0.1.msi\n", "a" * 64),
    ("ABCDEF" + "0" * 58, "abcdef" + "0" * 58),
    ("pas d'empreinte", None), ("", None),
])
def test_empreinte_attendue(texte, attendu):
    assert mise_a_jour.empreinte_attendue(texte) == attendu


# --- GitHub simulé ---------------------------------------------------------------------------------------
MSI = b"contenu du faux installeur"


@pytest.fixture
def github(monkeypatch):
    etat = {"tag": "v9.9.9", "msi": MSI, "sha": hashlib.sha256(MSI).hexdigest() + "  LMAgent-9.9.9.msi",
            "assets": ["LMAgent-9.9.9.msi", "LMAgent-9.9.9.msi.sha256"], "demandes": []}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        etat["demandes"].append(url)
        if url.startswith("https://api.github.com/"):
            return R(json.dumps({"tag_name": etat["tag"], "assets": [
                {"name": n, "browser_download_url": f"https://github.com/telecharger/{n}"} for n in etat["assets"]]}).encode())
        if url.endswith(".sha256"):
            return R(etat["sha"].encode())
        if url.endswith(".msi"):
            return R(etat["msi"])
        raise AssertionError(url)
    monkeypatch.setattr(mise_a_jour.urllib.request, "urlopen", urlopen)
    return etat


@pytest.fixture
def installee(monkeypatch):
    monkeypatch.setattr(emplacements, "INSTALLEE", True)
    lances = []
    monkeypatch.setattr(mise_a_jour, "lancer_installation", lambda msi: lances.append(msi))
    return lances


def test_derniere_version(github):
    info = mise_a_jour.derniere_version("moi/depot")
    assert info["version"] == "v9.9.9" and info["nom"] == "LMAgent-9.9.9.msi"
    assert info["msi"].endswith(".msi") and info["sha256"].endswith(".sha256")
    assert github["demandes"][0] == "https://api.github.com/repos/moi/depot/releases/latest"


def test_version_sans_installeur(github):
    github["assets"] = ["sources.zip"]
    assert mise_a_jour.derniere_version("moi/depot") is None


def test_version_sans_empreinte(github):
    github["assets"] = ["LMAgent-9.9.9.msi"]
    assert mise_a_jour.derniere_version("moi/depot") is None


def test_preparer_empreinte_correcte(github, tmp_path):
    msi = mise_a_jour.preparer(mise_a_jour.derniere_version("x/y"), tmp_path)
    assert msi.read_bytes() == MSI


def test_preparer_empreinte_falsifiee(github, tmp_path):
    github["msi"] = b"installeur modifie par un pirate"
    with pytest.raises(ValueError, match="empreinte"):
        mise_a_jour.preparer(mise_a_jour.derniere_version("x/y"), tmp_path)
    assert list(tmp_path.iterdir()) == []                     # fichier douteux supprimé


def test_preparer_empreinte_illisible(github, tmp_path):
    github["sha"] = "rien"
    with pytest.raises(ValueError, match="illisible"):
        mise_a_jour.preparer(mise_a_jour.derniere_version("x/y"), tmp_path)


class TestVerifier:
    def test_depuis_le_code_jamais(self, github, monkeypatch):
        monkeypatch.setattr(emplacements, "INSTALLEE", False)
        lancee, msg = mise_a_jour.verifier()
        assert not lancee and "git" in msg and github["demandes"] == []

    def test_nouvelle_version_installee(self, github, installee):
        lancee, msg = mise_a_jour.verifier(journal=lambda m: None)
        assert lancee and "9.9.9" in msg
        assert len(installee) == 1 and installee[0].read_bytes() == MSI

    def test_deja_a_jour(self, github, installee):
        github["tag"] = "v0.0.1"
        lancee, msg = mise_a_jour.verifier()
        assert not lancee and "à jour" in msg and installee == []

    def test_sans_appliquer(self, github, installee):
        lancee, msg = mise_a_jour.verifier(appliquer=False)
        assert not lancee and "disponible" in msg and installee == []

    def test_installeur_falsifie_rien_n_est_installe(self, github, installee):
        github["msi"] = b"pirate"
        lancee, msg = mise_a_jour.verifier()
        assert not lancee and "abandonnée" in msg and installee == []

    def test_sans_reseau(self, installee):
        lancee, msg = mise_a_jour.verifier()            # réseau bloqué par les tests
        assert not lancee and "impossible" in msg


class TestReglages:
    def ecrire(self, d):
        emplacements.config_agent().write_text(json.dumps(d), encoding="utf-8")

    def test_par_defaut(self):
        self.ecrire({})
        assert mise_a_jour.reglages() == (True, mise_a_jour.DEPOT_DEFAUT)

    def test_desactive_et_autre_depot(self):
        self.ecrire({"mises_a_jour_auto": False, "mises_a_jour_depot": "autre/depot"})
        assert mise_a_jour.reglages() == (False, "autre/depot")

    def test_au_demarrage_desactive(self, github, installee):
        self.ecrire({"mises_a_jour_auto": False})
        assert mise_a_jour.au_demarrage(journal=lambda m: None) is False
        assert github["demandes"] == [] and installee == []

    def test_au_demarrage_active(self, github, installee):
        self.ecrire({"mises_a_jour_auto": True})
        assert mise_a_jour.au_demarrage(journal=lambda m: None) is True

    def test_au_demarrage_depuis_le_code(self, github, monkeypatch):
        monkeypatch.setattr(emplacements, "INSTALLEE", False)
        assert mise_a_jour.au_demarrage(journal=lambda m: None) is False


def test_bouton_verifier_maintenant(client, monkeypatch):
    monkeypatch.setattr(emplacements, "INSTALLEE", False)
    r = client.post("/api/mise_a_jour", json={}).get_json()
    assert r["ok"] and not r["redemarrage"] and "git" in r["message"]
    h = client.get("/parametres").get_data(as_text=True)
    assert 'id="pli-version"' in h and "version" in h


def test_lancer_installation_commande(monkeypatch, tmp_path):
    vu = {}
    monkeypatch.setattr(mise_a_jour.subprocess, "Popen", lambda cmd, **k: vu.update(cmd=cmd))
    mise_a_jour.lancer_installation(tmp_path / "LMAgent-9.9.9.msi")
    script = vu["cmd"][-1]
    assert "Wait-Process" in script and "msiexec" in script and "/qn" in script and "LMAgent-9.9.9.msi" in script
