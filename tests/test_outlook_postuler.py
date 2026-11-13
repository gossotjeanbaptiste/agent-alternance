"""Fonctions d'Outlook qui ne demandent pas le logiciel (outlook.py) et assistant de candidature (postuler.py)."""
from types import SimpleNamespace

import pytest

import commun
import outlook
import postuler
import reponses


# --- outlook.texte_mail ------------------------------------------------------------------------------
class TestTexteMail:
    def test_signature_coupee(self):
        corps = "Madame, Monsieur,\r\n\r\n" + "Texte. " * 50 + "\r\nCordialement,\r\nCamille Test\r\nÉtudiante\r\n06…"
        t = outlook.texte_mail(SimpleNamespace(Body=corps))
        assert t.endswith("Cordialement,") and "Étudiante" not in t and "\r" not in t

    def test_nom_cite_au_debut_non_coupe(self):
        corps = "Camille Test\nvous écrit.\n" + "x" * 50
        assert "vous écrit" in outlook.texte_mail(SimpleNamespace(Body=corps))   # avant 200 caractères : gardé

    def test_lignes_vides_reduites_et_longueur(self):
        t = outlook.texte_mail(SimpleNamespace(Body="a\n\n\n\n\nb" + "c" * 5000), maxi=100)
        assert "a\n\nb" in t and len(t) == 100

    def test_sans_debut_de_signature(self, cfg):
        cfg["debut_signature"] = ""
        assert outlook.texte_mail(SimpleNamespace(Body="Corps\nCamille Test\nÉtudiante")) == \
            "Corps\nCamille Test\nÉtudiante"

    def test_mail_illisible(self):
        class Casse:
            @property
            def Body(self):
                raise OSError("COM")
        assert outlook.texte_mail(Casse()) == ""
        assert outlook.texte_mail(None) == ""


class TestAdresseOutlook:
    def test_adresse_smtp(self):
        assert outlook.Outlook._addr(SimpleNamespace(Address="Jean@Exemple.FR")) == "jean@exemple.fr"

    def test_utilisateur_exchange(self):
        ex = SimpleNamespace(PrimarySmtpAddress="Rh@Boite.fr")
        r = SimpleNamespace(Address="/o=ExchangeLabs/cn=x", AddressEntry=SimpleNamespace(GetExchangeUser=lambda: ex))
        assert outlook.Outlook._addr(r) == "rh@boite.fr"

    def test_destinataire_non_resolu(self):
        r = SimpleNamespace(Address="", AddressEntry=SimpleNamespace(GetExchangeUser=lambda: None),
                            Name="'contact@boite.fr'")
        assert outlook.Outlook._addr(r) == "contact@boite.fr"

    def test_rien_d_exploitable(self):
        assert outlook.Outlook._addr(SimpleNamespace(Address="", Name="Jean Dupont",
                                                     AddressEntry=SimpleNamespace(GetExchangeUser=lambda: None))) == ""
        assert outlook.Outlook._addr(object()) == ""


def test_chemins_outlook_reglables(cfg):
    assert [p.name for p in outlook._chemins_outlook()] == ["OUTLOOK.EXE", "OUTLOOK.EXE"]
    cfg["outlook"] = {"chemins_exe": [r"D:\Office\OUTLOOK.EXE"]}
    assert [str(p) for p in outlook._chemins_outlook()] == [r"D:\Office\OUTLOOK.EXE"]


def test_msg_corps_lu_a_la_demande():
    lus = []

    class Ns:
        def GetItemFromID(self, i):
            lus.append(i)
            return SimpleNamespace(Body="x" * 5000)
    m = outlook.Msg(Ns(), id="ID1", sujet="s")
    assert lus == []
    assert len(m["corps"]) == 4000 and lus == ["ID1"]
    m["corps"]
    assert lus == ["ID1"]                       # gardé en mémoire
    with pytest.raises(KeyError):
        m["autre"]


# --- postuler.py --------------------------------------------------------------------------------------
class TestPostuler:
    def test_signature_texte(self):
        assert postuler.signature().splitlines() == ["Camille Test", "Étudiante", "+33 6 00 00 00 00",
                                                     "camille@exemple.fr", "LinkedIn : https://linkedin.com/in/camille"]

    def test_signature_vide(self, cfg):
        cfg["signature_formulaire"] = {}
        assert postuler.signature() == ""

    @pytest.mark.parametrize("corps, attendu", [
        ("Lien pour postuler : https://x\n\nMadame,\n\nLettre.\n\nCordialement,\nCamille\nÉtudiante",
         "Madame,\n\nLettre.\n\nCordialement,"),
        ("Bonjour,\r\n\r\n\r\n\r\nTexte", "Bonjour,\n\nTexte"),
        ("Sans formule de fin", "Sans formule de fin"),
    ])
    def test_nettoyer(self, corps, attendu):
        assert postuler.nettoyer(corps) == attendu

    def test_nettoyer_en_gardant_la_signature(self):
        corps = "Madame,\n\nCordialement,\nCamille Test"
        assert postuler.nettoyer(corps, garder_signature=True) == corps

    def test_lettres_des_brouillons_et_du_fichier(self, monkeypatch, messagerie):
        textes = [("[À postuler sur La Bonne Alternance] Candidature",
                   "Lien pour postuler : https://lba/1\n\nLettre LBA.\n\nCordialement,\nsig", []),
                  ("Candidature développeur", "Madame,\n\nMail.\n\nCordialement,\nCamille", ["RH@Boite.fr"]),
                  ("[À postuler] sans lien", "Pas de lien ici", [])]
        import messagerie as mod
        monkeypatch.setattr(mod, "ouvrir", lambda: messagerie(textes=textes))
        reponses.enregistrer_lettre("https://site/contact", "Lettre du fichier.\n\nCordialement,\nsig")
        l = postuler.lettres_des_brouillons()
        assert l["https://lba/1"] == "Lettre LBA.\n\nCordialement,"
        assert l["rh@boite.fr"].endswith("Camille")              # brouillon de mail : signature gardée
        assert l["https://site/contact"] == "Lettre du fichier.\n\nCordialement,"
        assert len(l) == 3

    def test_lettres_sans_ouvrir_la_messagerie(self, monkeypatch):
        import messagerie as mod
        monkeypatch.setattr(mod, "ouvrir", lambda: pytest.fail("la messagerie ne doit pas être ouverte"))
        reponses.enregistrer_lettre("https://x", "L")
        assert postuler.lettres_des_brouillons(lire_messagerie=False) == {"https://x": "L"}

    def test_messagerie_indisponible(self, monkeypatch):
        import messagerie as mod

        def panne():
            raise OSError("Outlook ne répond pas")
        monkeypatch.setattr(mod, "ouvrir", panne)
        assert postuler.lettres_des_brouillons() == {}

    def test_reponses_de_deja_ecrites(self, tableau, monkeypatch):
        monkeypatch.setattr(postuler, "preparer_modele", lambda: pytest.fail("pas de modèle nécessaire"))
        tableau.add(**{"Entreprise": "E", "Lien": "https://lba/e"})
        deja = {"https://lba/e": {"motivations": "M"}}
        assert postuler.reponses_de(tableau, next(tableau.rows()), deja) == {"motivations": "M"}

    def test_reponses_de_a_ecrire(self, tableau, monkeypatch):
        monkeypatch.setattr(postuler, "preparer_modele", lambda: None)
        monkeypatch.setattr(reponses, "rediger_reponses", lambda o: {"motivations": "Nouveau " + o["entreprise"]})
        tableau.add(**{"Entreprise": "E", "Lien": "https://lba/e"})
        deja = {"https://lba/e": {"lettre": "seulement la lettre"}}
        r = postuler.reponses_de(tableau, next(tableau.rows()), deja)
        assert r == {"lettre": "seulement la lettre", "motivations": "Nouveau E"}
        assert reponses.lire()["https://lba/e"]["motivations"] == "Nouveau E"

    def test_ecrire_reponses_manquantes(self, tableau, monkeypatch, capsys):
        monkeypatch.setattr(postuler, "preparer_modele", lambda: None)
        monkeypatch.setattr(reponses, "rediger_reponses", lambda o: {"motivations": "M"})
        reponses.enregistrer("https://lba/a", {"motivations": "déjà"})
        tableau.add(**{"Entreprise": "A", "Lien": "https://lba/a"})
        tableau.add(**{"Entreprise": "B", "Lien": "https://lba/b"})
        postuler.ecrire_reponses_manquantes(tableau, list(tableau.rows()))
        out = capsys.readouterr().out
        assert "1 entreprise(s) sans réponses" in out and "B" in out
        assert reponses.lire()["https://lba/a"]["motivations"] == "déjà"
