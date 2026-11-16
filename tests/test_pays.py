"""Sites d'entreprises en France seulement (alternance/src/pays.py et son usage dans sites.py).
Pages simulées : aucun accès réseau."""
import io

import pytest

import pays
import sites


@pytest.mark.parametrize("url, attendu", [
    ("https://www.xefi.fr/contact", "France"), ("https://exemple.re", "France"), ("exemple.bzh", "France"),
    ("https://groupe.lu", "Luxembourg"), ("https://boite.be/fr", "Belgique"), ("https://firma.ch", "Suisse"),
    ("https://company.us", "États-Unis"), ("https://exemple.co.uk", "Royaume-Uni"), ("https://x.zz", "pays « .zz »"),
    ("https://boite.com", ""), ("https://boite.net", ""), ("https://boite.eu", ""), ("https://boite.io", ""),
])
def test_pays_de_l_extension(url, attendu):
    assert pays.pays_de_l_extension(url) == attendu


LIEU = "12 rue X 69003 Lyon"


@pytest.mark.parametrize("texte, attendu, raison", [
    ("Nos bureaux : 69003 Lyon", True, "code postal 69003"),
    ("Retrouvez-nous à LYON", True, "ville Lyon"),
    ("Appelez le +33 4 72 00 00 00", True, "téléphone français"),
    ("Tél. 04.72.00.00.00", True, "téléphone français"),
    ("SARL au capital de 10 000 €, SIRET 123 456 789 00011", True, "SIRET / RCS"),
    ("RCS Lyon B 123 456 789", True, "SIRET / RCS"),
    ("R.C.S. Luxembourg B123456 – +352 26 00 00", False, "Luxembourg"),
    ("Bienvenue chez nous, entreprise de services numériques", False, "aucune preuve"),
    ("Contact : +32 2 123 45 67, Bruxelles, Belgique", False, "Belgique"),
    ("Office: 1200 Main Street, Austin TX, USA, +1 (512) 555-0100", False, "États-Unis"),
])
def test_verdict_extension_neutre(texte, attendu, raison):
    ok, pourquoi = pays.verdict("https://boite.com", [f"<p>{texte}</p>"], LIEU)
    assert ok is attendu and raison in pourquoi


def test_verdict_extension_suffit():
    assert pays.verdict("https://boite.fr", [], LIEU) == (True, "extension .fr")
    ok, raison = pays.verdict("https://boite.lu", ["69003 Lyon +33 4 72 00 00 00"], LIEU)   # même avec des preuves
    assert not ok and "Luxembourg" in raison


def test_telephone_belge_ou_suisse_pas_compte():
    assert pays.preuves_francaises("02 123 45 67", "") == []          # Belgique : 9 chiffres
    assert pays.preuves_francaises("021 123 45 67", "") == []         # Suisse


# --- dans sites.py ---------------------------------------------------------------------------------
@pytest.fixture
def faux_web(monkeypatch):
    pages = {}

    def lire(url, maxi=500_000):
        url = url.rstrip("/")
        if url not in pages:
            raise OSError("introuvable")
        contenu, final = pages[url] if isinstance(pages[url], tuple) else (pages[url], url)
        return contenu, final
    monkeypatch.setattr(sites, "_lire", lire)
    return pages


class TestExplorerSite:
    def test_redirection_vers_un_site_luxembourgeois(self, faux_web):
        faux_web["https://groupe.com"] = ('<a href="/contact">contact</a> jobs@groupe.lu', "https://www.groupe.lu/")
        r = sites.explorer_site("https://groupe.com", lieu=LIEU)
        assert r["site"] == "" and r["email"] == "" and r["formulaire"] == ""
        assert "Luxembourg" in r["ecarte"] and "groupe.lu" in r["ecarte"]

    def test_site_neutre_sans_preuve_ecarte(self, faux_web):
        faux_web["https://boite.com"] = '<form><textarea></textarea></form> contact@boite.com, Welcome!'
        r = sites.explorer_site("https://boite.com", lieu=LIEU)
        assert r["email"] == "" and r["formulaire"] == "" and "aucune preuve" in r["ecarte"]

    def test_preuve_dans_les_mentions_legales(self, faux_web):
        faux_web["https://boite.com"] = "contact@boite.com"
        faux_web["https://boite.com/mentions-legales"] = "Siège : 12 rue X, 69003 Lyon"
        r = sites.explorer_site("https://boite.com", lieu=LIEU)
        assert r["email"] == "contact@boite.com" and r["ecarte"] == ""

    def test_verification_desactivee(self, faux_web, cfg):
        cfg["sites"] = {"verifier_france": False}
        faux_web["https://groupe.lu"] = "jobs@groupe.lu"
        assert sites.explorer_site("https://groupe.lu", lieu=LIEU)["email"] == "jobs@groupe.lu"


class TestTrouverLeSite:
    def test_deviner_ecarte_l_homonyme_etranger(self, faux_web):
        """berger-levrault.com répond avec le bon nom, mais c'est une entreprise des États-Unis : on n'en veut pas."""
        faux_web["https://bergerlevrault.fr"] = ("Autre chose", "https://bergerlevrault.fr")
        faux_web["https://bergerlevrault.com"] = ("Berger Levrault Inc., Austin TX, USA", "https://bergerlevrault.com")
        faux_web["https://berger-levrault.fr"] = ("<h1>Berger-Levrault</h1>", "https://www.berger-levrault.fr/")
        assert sites.deviner_site("Berger Levrault", LIEU) == "https://www.berger-levrault.fr"

    def test_recherche_ecarte_les_resultats_etrangers(self, monkeypatch, faux_web):
        monkeypatch.setattr(sites.time, "sleep", lambda s: None)
        monkeypatch.setitem(sites.RECHERCHE, "bloquee", False)
        monkeypatch.setattr(sites, "deviner_site", lambda nom, lieu="": "")

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        resultats = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fopticod.lu">a</a>'
                     '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fopticod.com">b</a>'
                     '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.opticod.net">c</a>')
        monkeypatch.setattr(sites.urllib.request, "urlopen", lambda *a, **k: R(resultats.encode()))
        faux_web["https://opticod.com"] = "Opticod — English only"
        faux_web["https://www.opticod.net"] = "Opticod, 69003 Lyon"
        assert sites.trouver_site("Opticod", LIEU) == "https://www.opticod.net"


def test_journal_quand_un_site_est_ecarte(monkeypatch, tableau, messagerie, capsys):
    import candidatures
    o = {"entreprise": "Boite Lux", "poste": "Candidature spontanée", "lieu": LIEU, "contact": "", "email": "",
         "site": "https://groupe.lu", "lien": "", "infos": "", "source": "La Bonne Alternance (Lyon)",
         "lba_postulable": False, "siret": "1"}
    monkeypatch.setattr(candidatures, "depuis_a_contacter", lambda s: [])
    monkeypatch.setattr(candidatures, "depuis_linkedin", lambda ol: [])
    monkeypatch.setattr(candidatures, "depuis_lba", lambda: iter([o]))
    monkeypatch.setattr(candidatures, "explorer_site", lambda site, **k: {
        "site": "", "email": "", "formulaire": "", "ecarte": "site d'un autre pays (Luxembourg, .lu) : https://groupe.lu"})
    monkeypatch.setattr(candidatures, "rediger_candidature", lambda o: ("Objet", "Madame, Monsieur,\n\nTexte."))
    candidatures.nouvelles_candidatures(tableau, messagerie())
    assert "🌍 Boite Lux : site écarté (site d'un autre pays (Luxembourg, .lu)" in capsys.readouterr().out
