"""Contre-prompt, signature des mails, chemins (alternance/src/commun.py), appels au modèle (modele.py)
et choix de la messagerie (messagerie.py)."""
from pathlib import Path

import pytest

import agent
import commun
import messagerie
import modele


class TestInterdits:
    def ecrire(self, texte):
        commun.INTERDITS.write_text(texte, encoding="utf-8")

    @pytest.fixture(autouse=True)
    def sauvegarde(self):
        avant = commun.INTERDITS.read_text(encoding="utf-8") if commun.INTERDITS.exists() else None
        yield
        if avant is None:
            commun.INTERDITS.unlink(missing_ok=True)
        else:
            commun.INTERDITS.write_text(avant, encoding="utf-8")

    def test_regles_listees(self):
        self.ecrire("# Titre\n> explication\n\n- Pas d'émojis\nPas de « passionné »\n* Rien inventer\n")
        t = commun.interdits()
        assert t.startswith("\n\nINTERDIT")
        assert "- Pas d'émojis" in t and "- Pas de « passionné »" in t and "* Rien inventer" in t
        assert "Titre" not in t and "explication" not in t

    def test_fichier_sans_regle(self):
        self.ecrire("# juste un titre\n> et une aide\n\n")
        assert commun.interdits() == ""

    def test_fichier_absent(self):
        commun.INTERDITS.unlink()
        assert commun.interdits() == ""

    def test_relu_a_chaque_appel(self):
        self.ecrire("- règle A\n")
        assert "règle A" in commun.interdits()
        self.ecrire("- règle B\n")
        assert "règle B" in commun.interdits() and "règle A" not in commun.interdits()


class TestSignatureMail:
    def test_desactivee(self, cfg):
        cfg["ajouter_signature"] = False
        assert commun.signature_mail() == ""

    def test_construite_depuis_la_signature_formulaire(self, cfg):
        cfg["ajouter_signature"] = True
        s = commun.signature_mail()
        assert "<b>Camille Test</b>" in s
        assert "camille@exemple.fr" in s
        assert "LinkedIn : <a href='https://linkedin.com/in/camille'>" in s
        assert "Portfolio" not in s and "GitHub" not in s     # vides : non affichés

    def test_caracteres_echappes(self, cfg):
        cfg["ajouter_signature"] = True
        cfg["signature_formulaire"] = {"nom": "<script>x</script>"}
        assert "<script>" not in commun.signature_mail()

    def test_fichier_html_prioritaire(self, cfg, tmp_path):
        cfg["ajouter_signature"] = True
        f = tmp_path / "sig.htm"
        f.write_text("<p>Ma signature HTML</p>", encoding="utf-8")
        assert commun.signature_mail(str(f)) == "<p>Ma signature HTML</p>"

    def test_fichier_outlook_sans_balise_charset(self, cfg, tmp_path):
        """La balise charset de la signature Outlook cassait les accents de tout le mail."""
        cfg["ajouter_signature"] = True
        f = tmp_path / "sig.htm"
        f.write_text('<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
                     "<p>Étudiant à Lyon</p>", encoding="utf-8")
        assert commun.signature_mail(str(f)) == "<p>Étudiant à Lyon</p>"

    def test_fichier_windows_1252_page_complete(self, cfg, tmp_path):
        cfg["ajouter_signature"] = True
        f = tmp_path / "sig.htm"
        f.write_bytes("<html><head><meta charset=windows-1252><style>p{}</style></head>"
                      "<body lang=FR><p>Camille Test, 3ème année</p></body></html>".encode("cp1252"))
        assert commun.signature_mail(str(f)) == "<p>Camille Test, 3ème année</p>"

    def test_fichier_introuvable_signature_construite(self, cfg, tmp_path):
        cfg["ajouter_signature"] = True
        assert "Camille Test" in commun.signature_mail(str(tmp_path / "absent.htm"))

    def test_signature_vide(self, cfg):
        cfg["ajouter_signature"] = True
        cfg["signature_formulaire"] = {}
        assert commun.signature_mail() == ""


def test_P_developpe_le_dossier_utilisateur():
    assert commun.P("~/x.txt") == Path.home() / "x.txt"


class TestModele:
    @pytest.fixture
    def reponse(self, monkeypatch):
        class Reponse:
            texte = ""
            envoyes = []
        r = Reponse()
        r.envoyes = []

        def post_chat(corps):
            r.envoyes.append(corps)
            return {"content": r.texte}
        monkeypatch.setattr(agent, "post_chat", post_chat)
        return r

    def test_llm_sans_reflexion_par_defaut(self, reponse, cfg):
        reponse.texte = "  bonjour  "
        assert modele.llm("question") == "bonjour"
        corps = reponse.envoyes[0]
        assert corps["reasoning_effort"] == "none"
        assert corps["messages"][-1]["content"] == "question"

    def test_llm_avec_reflexion(self, reponse, cfg):
        cfg["reflexion"] = True
        reponse.texte = "ok"
        modele.llm("q")
        assert "reasoning_effort" not in reponse.envoyes[0]

    def test_llm_reponse_vide(self, reponse):
        reponse.texte = None
        assert modele.llm("q") == ""

    @pytest.mark.parametrize("texte, attendu", [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 2}\n```', {"a": 2}),
        ('Voici : {"a": 3} voilà', {"a": 3}),
        ('[{"entreprise": "X"}]', [{"entreprise": "X"}]),
        ('texte\n```\n["a", "b"]\n```', ["a", "b"]),
    ])
    def test_llm_json(self, reponse, texte, attendu):
        reponse.texte = texte
        assert modele.llm_json("q") == attendu
        assert "UNIQUEMENT avec du JSON" in reponse.envoyes[-1]["messages"][-1]["content"]

    def test_llm_json_invalide(self, reponse):
        reponse.texte = "pas de json ici"
        with pytest.raises(ValueError, match="illisible"):
            modele.llm_json("q")
        assert len(reponse.envoyes) == 2                                   # redemandé une fois avant d'abandonner
        assert "n'était pas du JSON valide" in reponse.envoyes[1]["messages"][-1]["content"]

    def test_llm_json_redemande_puis_reussit(self, reponse, monkeypatch):
        reponses = iter(["{ cassé", '{"motivations": "M"}'])
        monkeypatch.setattr(agent, "post_chat", lambda corps: reponse.envoyes.append(corps) or {"content": next(reponses)})
        assert modele.llm_json("q") == {"motivations": "M"} and len(reponse.envoyes) == 2

    @pytest.mark.parametrize("texte, attendu", [
        # erreur réelle d'une routine : virgule avant l'accolade fermante (« Expecting property name… line 5 »)
        ('{\n "motivations": "M",\n "missions": "Mi",\n "experiences": "E",\n}', {"motivations": "M", "missions": "Mi",
                                                                                "experiences": "E"}),
        ('["a", "b",]', ["a", "b"]),
        ('{"lettre": "Madame,\nBonjour"}', {"lettre": "Madame,\nBonjour"}),                 # retour à la ligne brut
        ('{“objet”: “Candidature”}', {"objet": "Candidature"}),                            # guillemets typographiques
        ("{'objet': 'Candidature', 'corps': 'Texte'}", {"objet": "Candidature", "corps": "Texte"}),
        ('{"citation": "il a dit \\"oui\\"", }', {"citation": 'il a dit "oui"'}),
    ])
    def test_lire_json_tolerant(self, texte, attendu):
        assert modele.lire_json(texte) == attendu


class TestMessagerie:
    def test_outlook_par_defaut(self, cfg):
        cfg.pop("messagerie", None)
        assert messagerie.type_messagerie() == "outlook"
        assert messagerie.nom_messagerie() == "Outlook"

    def test_imap(self, cfg):
        cfg["messagerie"] = {"type": "IMAP"}
        assert messagerie.type_messagerie() == "imap"
        assert messagerie.nom_messagerie() == "ta messagerie"

    def test_ouvrir_imap_sans_reglages_refuse(self, cfg):
        cfg["messagerie"] = {"type": "imap", "imap": {}}
        with pytest.raises(SystemExit) as e:
            messagerie.ouvrir()
        assert "serveur" in str(e.value) and "mot_de_passe_app" in str(e.value)
