"""Outils sur les adresses et le texte des mails (alternance/src/mails.py)."""
import pytest

import mails


@pytest.mark.parametrize("adresse, attendu", [
    ("contact@exemple.fr", True),
    ("Prenom.Nom@Exemple.COM", True),
    ("  rh@societe.io  ", True),
    ("a+filtre@sous.domaine.org", True),
    ("pas-une-adresse", False),
    ("sans@extension", False),
    ("deux@@arobases.fr", False),
    ("espace dans@adresse.fr", False),
    ("search@0.0.206", False),          # adresse trouvée sur un site, sans vraie extension
    ("", False),
    (None, False),
    ("labonnealternance", False),
    ("x@y.f", False),                   # extension d'une seule lettre
])
def test_est_adresse(adresse, attendu):
    assert mails.est_adresse(adresse) is attendu


@pytest.mark.parametrize("adresse, attendu", [
    ("contact@Exemple.FR", "exemple.fr"),
    ("a@b.sous.domaine.com", "b.sous.domaine.com"),
    ("pas une adresse", ""),
    ("", ""),
])
def test_domaine(adresse, attendu):
    assert mails.domaine(adresse) == attendu


@pytest.mark.parametrize("adresse, attendu", [
    ("contact@exemple.fr", True),
    ("RH@exemple.fr", True),
    ("recrutement.lyon@exemple.fr", True),    # « recrutement » avant le point
    ("jobs@exemple.fr", True),
    ("prenom.nom@exemple.fr", False),
    ("camille@exemple.fr", False),
    ("", False),
    (None, False),
])
def test_est_generique(adresse, attendu):
    assert mails.est_generique(adresse) is attendu


def test_domaines_perso_et_generiques_viennent_des_reglages():
    import reglages
    assert mails.DOMAINES_PERSO == set(reglages.DOMAINES_PERSO)
    assert mails.GENERIQUES == tuple(reglages.GENERIQUES)
    assert "gmail.com" in mails.DOMAINES_PERSO


class TestTexteVersHtml:
    def test_paragraphes(self):
        h = mails.texte_vers_html("Bonjour,\n\nPremier paragraphe.\n\nCordialement,")
        assert h.count("<p ") == 3
        assert "Premier paragraphe." in h

    def test_retours_a_la_ligne_dans_un_paragraphe(self):
        h = mails.texte_vers_html("ligne 1\nligne 2")
        assert "ligne 1<br>ligne 2" in h
        assert h.count("<p ") == 1

    def test_caracteres_html_echappes(self):
        h = mails.texte_vers_html("a < b & c > d")
        assert "a &lt; b &amp; c &gt; d" in h
        assert "<b" not in h.replace("<br>", "")

    def test_lignes_vides_multiples_et_espaces(self):
        h = mails.texte_vers_html("  A\n\n\n   \n\nB  ")
        assert h.count("<p ") == 2

    def test_texte_vide(self):
        assert mails.texte_vers_html("").count("<p ") == 1
