"""Sites des entreprises : trouver le site, une adresse ou un formulaire de contact (alternance/src/sites.py).
Le réseau est simulé : _lire (pages des sites) et urlopen (recherche web) sont remplacés."""
import io

import pytest

import sites


# --- outils sur les noms -----------------------------------------------------------------------
@pytest.mark.parametrize("nom, attendu", [
    ("E.S.I. France", ["esi", "france"]),
    ("N Tech Services", ["n", "tech", "services"]),
    ("Lambert Morel", ["lambert", "morel"]),
    ("A B", ["ab"]),
    ("", []),
])
def test_mots_nom(nom, attendu):
    assert sites._mots_nom(nom) == attendu


@pytest.mark.parametrize("nom, attendu", [
    ("Lambert Morel", ["lambert", "morel"]),
    ("SARL Opticod", ["opticod"]),
    ("E.S.I. France", ["esi"]),                 # « France » est générique
    ("N Tech Services", ["tech"]),
    ("Groupe France Services", []),             # que des mots génériques
])
def test_mots(nom, attendu):
    assert sites._mots(nom) == attendu


@pytest.mark.parametrize("nom, url, attendu", [
    ("Lambert Morel", "https://www.lambert-morel.com/fr/", True),
    ("Opticod", "https://groupe-opticod.fr/", True),
    ("Unidoc", "https://unidoc.fr", True),
    ("Unidoc", "https://unidoctor.com", True),          # contient le nom : accepté (limite connue)
    ("Opticod", "https://www.societe.com/opticod", False),     # annuaire
    ("Opticod", "https://fr.linkedin.com/company/opticod", False),
    ("N Tech Services", "https://www.pagesjaunes.fr/x", False),
    ("Lambert Morel", "https://www.autre-site.fr", False),
    ("Exemple", "", False),
])
def test_ressemble(nom, url, attendu):
    assert sites.ressemble(nom, url) is attendu


@pytest.mark.parametrize("lieu, attendu", [
    ("12 rue X 69003 Lyon", ("69003", "lyon")),
    ("3 rue Desaix 67450 MUNDOLSHEIM", ("67450", "mundolsheim")),
    ("Villeurbanne", ("", "villeurbanne")),
    ("", ("", "")),
])
def test_repere_lieu(lieu, attendu):
    assert sites._repere_lieu(lieu) == attendu


# --- adresses et formulaires dans une page ------------------------------------------------------
class TestAdresses:
    def test_adresse_simple_et_mailto(self):
        h = '<a href="mailto:contact@exemple.fr">Écrire</a> ou rh@exemple.fr'
        assert sorted(sites._adresses(h, "exemple.fr")) == ["contact@exemple.fr", "rh@exemple.fr"]

    def test_adresse_masquee(self):
        h = "contact [at] exemple [dot] fr — jobs (arobase) exemple (point) fr"
        assert sorted(sites._adresses(h, "exemple.fr")) == ["contact@exemple.fr", "jobs@exemple.fr"]

    def test_protection_cloudflare(self):
        # « contact@exemple.fr » chiffré comme le fait Cloudflare (clé 0x42)
        cle = 0x42
        code = f"{cle:02x}" + "".join(f"{ord(c) ^ cle:02x}" for c in "contact@exemple.fr")
        assert sites._cloudflare(code) == "contact@exemple.fr"
        assert sites._adresses(f'<span data-cfemail="{code}">[email protected]</span>', "exemple.fr") == ["contact@exemple.fr"]

    def test_autre_domaine_ignore_sauf_grand_public(self):
        h = "agence@webagency.com contact.boite@gmail.com rh@exemple.fr"
        assert sorted(sites._adresses(h, "exemple.fr")) == ["contact.boite@gmail.com", "rh@exemple.fr"]

    def test_faux_positifs_ecartes(self):
        h = "logo@2x.png icone@3x.webp x@sentry.io test@example.com search@0.0.206 a@exemple.fr"
        assert sites._adresses(h, "exemple.fr") == ["a@exemple.fr"]

    def test_sous_domaine_accepte(self):
        assert sites._adresses("rh@mail.exemple.fr", "exemple.fr") == ["rh@mail.exemple.fr"]


class TestFormulaire:
    @pytest.mark.parametrize("html, attendu", [
        ('<form action="/c"><input name="nom"><textarea name="message"></textarea></form>', True),
        ('<form role="search"><input type="search"><textarea></textarea></form>', False),
        ('<form><input name="email"></form>', False),          # pas de champ de message
        ('<div class="wpcf7">…</div>', True),                  # extension WordPress
        ('<script src="https://js.hsforms.net"></script><script>hbspt.forms.create({})</script>', True),
        ('<p>Pas de formulaire</p>', False),
    ])
    def test_detection(self, html, attendu):
        assert sites._a_un_formulaire(html) is attendu


def test_liens_contact_tries_et_meme_site():
    h = ('<a href="/mentions-legales">Mentions</a><a href="/nous-contacter">Contact</a>'
         '<a href="https://autre.fr/contact">ailleurs</a><a href="mailto:x@y.fr">contact</a>'
         '<a href="/produits">Produits</a><a href="/recrutement">Rejoignez-nous</a>')
    liens = sites._liens_contact(h, "https://exemple.fr/")
    assert liens[0] == "https://exemple.fr/nous-contacter"
    assert "https://exemple.fr/recrutement" in liens
    assert liens[-1] == "https://exemple.fr/mentions-legales"
    assert all("autre.fr" not in l and "mailto" not in l and "produits" not in l for l in liens)


# --- exploration d'un site (pages simulées) ------------------------------------------------------
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
    def test_adresse_et_formulaire(self, faux_web):
        faux_web["https://exemple.fr"] = '<a href="/contact">Contact</a> info@exemple.fr'
        faux_web["https://exemple.fr/contact"] = ('<form><textarea name="m"></textarea></form>'
                                                  ' recrutement@exemple.fr')
        r = sites.explorer_site("exemple.fr")
        assert r["email"] == "recrutement@exemple.fr"         # préférée à info@
        assert r["formulaire"] == "https://exemple.fr/contact"
        assert r["site"] == "https://exemple.fr"

    def test_preference_des_adresses(self, faux_web):
        faux_web["https://exemple.fr"] = "zz@exemple.fr contact@exemple.fr direction@exemple.fr"
        assert sites.explorer_site("https://exemple.fr")["email"] == "contact@exemple.fr"

    def test_adresse_du_domaine_avant_grand_public(self, faux_web):
        faux_web["https://exemple.fr"] = "contact@gmail.com contact@exemple.fr"
        assert sites.explorer_site("https://exemple.fr")["email"] == "contact@exemple.fr"

    def test_formulaire_sur_l_accueil(self, faux_web):
        faux_web["https://exemple.fr"] = '<form><textarea></textarea></form>'
        r = sites.explorer_site("https://exemple.fr")
        assert r["formulaire"] == "https://exemple.fr" and r["email"] == ""

    def test_lien_de_formulaire_sans_parametres(self, faux_web):
        faux_web["https://exemple.fr"] = '<a href="/contact?source=menu&x=1">Contact</a>'
        faux_web["https://exemple.fr/contact?source=menu&x=1"] = '<form><textarea></textarea></form>'
        assert sites.explorer_site("https://exemple.fr")["formulaire"] == "https://exemple.fr/contact"

    def test_site_injoignable(self, faux_web):
        assert sites.explorer_site("https://injoignable.fr") == {"site": "https://injoignable.fr", "email": "",
                                                                 "formulaire": "", "ecarte": ""}

    def test_site_vide(self):
        assert sites.explorer_site("") == {"site": "", "email": "", "formulaire": "", "ecarte": ""}

    def test_redirection_suivie(self, faux_web):
        faux_web["https://exemple.fr"] = ("contact@exemple.com, tél. 04 72 00 00 00", "https://www.exemple.com/")
        r = sites.explorer_site("https://exemple.fr")
        assert r["site"] == "https://www.exemple.com/" and r["email"] == "contact@exemple.com"

    def test_nombre_de_pages_limite(self, faux_web, cfg):
        cfg["sites"] = {"pages_max": 2}
        liens = "".join(f'<a href="/contact{i}">contact {i}</a>' for i in range(10))
        faux_web["https://exemple.fr"] = liens
        lues = []
        vrai = sites._lire

        def compte(url, maxi=500_000):
            lues.append(url)
            return vrai(url, maxi)
        import pytest as _p  # noqa: F401
        sites_lire = compte
        orig = sites._lire
        sites._lire = sites_lire
        try:
            sites.explorer_site("https://exemple.fr")
        finally:
            sites._lire = orig
        assert len(lues) <= 3      # accueil + 2 pages


class TestDevinerSite:
    def test_domaine_evident(self, faux_web):
        faux_web["https://lambertmorel.fr"] = ("Autre chose", "https://lambertmorel.fr")
        faux_web["https://lambert-morel.com"] = ("<h1>Lambert-Morel</h1> éditeur, RCS Toulouse",
                                                   "https://www.lambert-morel.com/")
        assert sites.deviner_site("Lambert Morel") == "https://www.lambert-morel.com"

    def test_redirection_vers_un_autre_site_refusee(self, faux_web):
        faux_web["https://opticod.fr"] = ("Opticod", "https://pass-tech.fr/")
        assert sites.deviner_site("Opticod") == ""

    def test_page_qui_ne_cite_pas_l_entreprise(self, faux_web):
        faux_web["https://unidoc.fr"] = ("Domaine à vendre", "https://unidoc.fr")
        assert sites.deviner_site("Unidoc") == ""

    def test_nom_court_ville_exigee(self, faux_web):
        faux_web["https://ntech.fr"] = ("NTech informatique à Paris", "https://ntech.fr")
        assert sites.deviner_site("N Tech Services", "3 rue Desaix 67450 MUNDOLSHEIM") == ""
        faux_web["https://ntech.fr"] = ("NTech informatique, 67450 Mundolsheim", "https://ntech.fr")
        assert sites.deviner_site("N Tech Services", "3 rue Desaix 67450 MUNDOLSHEIM") == "https://ntech.fr"

    def test_que_des_mots_generiques(self, faux_web):
        assert sites.deviner_site("Groupe France Services") == ""


class TestTrouverSite:
    @pytest.fixture(autouse=True)
    def sans_attente(self, monkeypatch):
        monkeypatch.setattr(sites.time, "sleep", lambda s: None)
        monkeypatch.setitem(sites.RECHERCHE, "bloquee", False)
        monkeypatch.setitem(sites.RECHERCHE, "derniere", 0.0)
        monkeypatch.setattr(sites, "deviner_site", lambda nom, lieu="": "")

    def reponse(self, monkeypatch, html):
        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        monkeypatch.setattr(sites.urllib.request, "urlopen", lambda *a, **k: R(html.encode()))

    def test_premier_resultat_qui_ressemble(self, monkeypatch):
        self.reponse(monkeypatch,
                     '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.societe.com%2Fopticod">x</a>'
                     '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fopticod.fr%2Fcontact">y</a>')
        assert sites.trouver_site("Opticod", "Lyon") == "https://opticod.fr"

    def test_page_anti_robot_bloque_les_recherches(self, monkeypatch):
        self.reponse(monkeypatch, "<html>anomaly detected</html>")
        assert sites.trouver_site("Opticod") == ""
        assert sites.RECHERCHE["bloquee"] is True
        appels = []
        monkeypatch.setattr(sites.urllib.request, "urlopen", lambda *a, **k: appels.append(1))
        assert sites.trouver_site("Autre") == ""
        assert appels == []          # plus aucune recherche pendant ce passage

    def test_erreur_reseau(self, monkeypatch):
        def erreur(*a, **k):
            raise OSError("pas de réseau")
        monkeypatch.setattr(sites.urllib.request, "urlopen", erreur)
        assert sites.trouver_site("Opticod") == ""

    def test_domaine_devine_sans_recherche(self, monkeypatch):
        monkeypatch.setattr(sites, "deviner_site", lambda nom, lieu="": "https://opticod.fr")
        appels = []
        monkeypatch.setattr(sites.urllib.request, "urlopen", lambda *a, **k: appels.append(1))
        assert sites.trouver_site("Opticod") == "https://opticod.fr"
        assert appels == []
