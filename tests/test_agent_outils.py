"""Outils de fichiers de l'agent (agent.py), mise à jour interactive du tableau (maj_tableau.py)
et générateur de logo (outils/generer_logo.py). Rien sur la tour ni sur le serveur LM Studio.
Tout se passe dans des dossiers temporaires."""
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

import agent
import maj_tableau
from tableau import C_FORMULAIRE, C_LBA, MAIL


# --- outils de fichiers de l'agent --------------------------------------------------------------------
@pytest.fixture
def bac(monkeypatch, tmp_path):
    """Workspace, corbeille et dossier autorisé temporaires ; mode automatique (pas de question)."""
    ws, corbeille, autorise = tmp_path / "workspace", tmp_path / "corbeille", tmp_path / "autorise"
    for d in (ws, corbeille, autorise):
        d.mkdir()
    monkeypatch.setattr(agent, "WORKSPACE", ws)
    monkeypatch.setattr(agent, "CORBEILLE", corbeille)
    monkeypatch.setattr(agent, "ALLOWED", [ws.resolve(), autorise.resolve()])
    monkeypatch.setattr(agent, "AUTO", True)
    monkeypatch.setitem(agent.CONFIG, "powershell_en_auto", False)
    return ws, corbeille, autorise


class TestSafePath:
    def test_chemin_relatif_dans_le_workspace(self, bac):
        ws, _, _ = bac
        assert agent._safe_path("dossier/f.txt") == (ws / "dossier" / "f.txt").resolve()

    def test_chemin_absolu_autorise(self, bac):
        _, _, autorise = bac
        assert agent._safe_path(str(autorise / "x.txt")) == (autorise / "x.txt").resolve()

    @pytest.mark.parametrize("chemin", ["../echappe.txt", "../../config.json", "C:/Windows/System32/x.dll"])
    def test_chemins_interdits(self, bac, chemin):
        with pytest.raises(PermissionError):
            agent._safe_path(chemin)

    def test_dossier_voisin_au_nom_proche_refuse(self, bac, tmp_path):
        with pytest.raises(PermissionError):
            agent._safe_path(str(tmp_path / "workspace_pirate" / "x"))


class TestOutils:
    def test_ecrire_lire(self, bac):
        assert "Fichier écrit" in agent.write_file("notes/a.txt", "bonjour")
        assert agent.read_file("notes/a.txt") == "bonjour"

    def test_reecriture_sauvegarde_l_ancienne_version(self, bac):
        ws, corbeille, _ = bac
        agent.write_file("a.txt", "v1")
        msg = agent.write_file("a.txt", "v2")
        assert "ancienne version" in msg and agent.read_file("a.txt") == "v2"
        assert [f.read_text(encoding="utf-8") for f in corbeille.iterdir()] == ["v1"]

    def test_lecture_tronquee(self, bac):
        agent.write_file("gros.txt", "x" * 30000)
        assert agent.read_file("gros.txt").endswith("[tronqué]")

    def test_lister(self, bac):
        agent.create_folder("sous")
        agent.write_file("b.txt", "x")
        l = agent.list_dir(".")
        assert "[D] sous/" in l and "[F] b.txt" in l
        assert "(dossier vide)" in agent.list_dir("sous")

    def test_deplacer(self, bac):
        agent.write_file("a.txt", "x")
        agent.create_folder("dest")
        assert "Déplacé" in agent.move_file("a.txt", "dest")
        assert agent.read_file("dest/a.txt") == "x"
        assert "Introuvable" in agent.move_file("a.txt", "dest")
        agent.write_file("c.txt", "y")
        agent.write_file("dest/c.txt", "z")
        assert "existe déjà" in agent.move_file("c.txt", "dest")

    def test_supprimer_va_a_la_corbeille(self, bac):
        ws, corbeille, _ = bac
        agent.write_file("a.txt", "x")
        assert "corbeille" in agent.delete_file("a.txt")
        assert not (ws / "a.txt").exists() and len(list(corbeille.iterdir())) == 1
        assert "Introuvable" in agent.delete_file("a.txt")

    def test_dossier_racine_autorise_protege(self, bac):
        ws, _, _ = bac
        assert "Interdit" in agent.delete_file(str(ws))

    def test_refus_de_l_utilisateur(self, bac, monkeypatch):
        monkeypatch.setattr(agent, "AUTO", False)
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        assert agent.write_file("a.txt", "x") == "Refusé par l'utilisateur."
        monkeypatch.setattr("builtins.input", lambda *a: "oui")
        assert "Fichier écrit" in agent.write_file("a.txt", "x")

    def test_powershell_interdit_en_automatique(self, bac):
        assert "Interdit en mode automatique" in agent.run_powershell("Get-ChildItem")

    def test_page_web_reseau_bloque(self, bac):
        import conftest
        with pytest.raises(conftest.ReseauInterdit):
            agent.fetch_url("https://exemple.fr")

    def test_schemas_des_outils(self):
        noms = {s["function"]["name"] for s in agent.TOOL_SCHEMAS}
        assert noms == set(agent.TOOLS)
        for s in agent.TOOL_SCHEMAS:
            p = s["function"]["parameters"]
            assert set(p["required"]) <= set(p["properties"])

    def test_consigne_systeme(self, bac, monkeypatch):
        assert "MODE AUTOMATIQUE" in agent.system_prompt()
        monkeypatch.setattr(agent, "AUTO", False)
        assert "Mode interactif" in agent.system_prompt()

    def test_journal(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(agent, "LOGS", tmp_path)
        agent.say("message de test")
        assert "message de test" in capsys.readouterr().out
        assert "message de test" in next(tmp_path.glob("*.log")).read_text(encoding="utf-8")


# --- mise à jour interactive du tableau ------------------------------------------------------------------
class TestMajTableau:
    @pytest.fixture
    def repondre(self, monkeypatch):
        def regler(*reponses):
            it = iter(reponses)
            monkeypatch.setattr("builtins.input", lambda *a: next(it))
        return regler

    def test_demander(self, repondre, monkeypatch):
        monkeypatch.setattr(maj_tableau, "VOIR", False)
        repondre("9", "2")
        assert maj_tableau.demander("Q ?", {"1": "a", "2": "b"}) == "2"      # « 9 » refusé, puis « 2 »
        repondre("")
        assert maj_tableau.demander("Q ?", {"1": "a"}) == ""

    def test_demander_en_lecture_seule(self, monkeypatch):
        monkeypatch.setattr(maj_tableau, "VOIR", True)
        monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("aucune question en mode --voir"))
        assert maj_tableau.demander("Q ?", {"1": "a"}) == ""

    def test_demander_date(self, repondre):
        repondre("")
        assert maj_tableau.demander_date(date(2026, 1, 2)) == date(2026, 1, 2)
        auj = date.today()
        hier = auj - timedelta(days=1)
        repondre(f"{hier:%d/%m}")
        assert maj_tableau.demander_date() == hier
        demain = auj + timedelta(days=1)
        repondre(f"{demain:%d-%m}")
        assert maj_tableau.demander_date() == demain.replace(year=demain.year - 1)   # date future -> année d'avant
        repondre("n'importe quoi")
        assert maj_tableau.demander_date(date(2026, 1, 2)) == date(2026, 1, 2)

    def test_appliquer_envoye_par_mail(self, tableau, repondre):
        tableau.add(**{"Entreprise": "A"})
        r, stats = next(tableau.rows()), {"réponses": 0, "passées": 0}
        repondre("")
        maj_tableau.appliquer_candidature(tableau, r, "1", stats)
        assert tableau.get(r, "Statut") == MAIL and tableau.get(r, "Relance prévue") is not None
        assert stats["réponses"] == 1

    @pytest.mark.parametrize("canal, statut", [("", C_LBA), ("formulaire du site", C_FORMULAIRE)])
    def test_appliquer_autre_canal(self, tableau, repondre, canal, statut):
        tableau.add(**{"Entreprise": "A", "Notes": "SIRET 1"})
        r = next(tableau.rows())
        repondre(canal, "")
        maj_tableau.appliquer_candidature(tableau, r, "2", {"réponses": 0, "passées": 0})
        assert tableau.get(r, "Statut") == statut
        assert tableau.get(r, "Notes").startswith("Candidature via :") and "SIRET 1" in tableau.get(r, "Notes")

    def test_appliquer_abandon_et_retrait(self, tableau, monkeypatch):
        monkeypatch.setattr(maj_tableau, "A_SUPPRIMER", [])
        tableau.add(**{"Entreprise": "A", "Relance prévue": "2026-11-20"})
        tableau.add(**{"Entreprise": "B"})
        a, b = list(tableau.rows())
        stats = {"réponses": 0, "passées": 0}
        maj_tableau.appliquer_candidature(tableau, a, "3", stats)
        assert tableau.get(a, "Statut") == "Abandonné" and tableau.get(a, "Relance prévue") is None
        maj_tableau.appliquer_candidature(tableau, b, "4", stats)
        assert maj_tableau.A_SUPPRIMER == [3]
        maj_tableau.appliquer_candidature(tableau, b, "", stats)
        assert stats == {"réponses": 2, "passées": 1}


# --- générateur de logo ----------------------------------------------------------------------------------
@pytest.fixture
def logo(monkeypatch, tmp_path):
    racine = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("generer_logo", racine / "outils" / "generer_logo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "SORTIE", tmp_path)
    return mod


class TestLogo:
    def test_carre_et_banniere(self, logo):
        from PIL import Image
        carre = logo.carre()
        assert carre.size == (256, 256) and carre.mode == "RGBA"
        assert carre.getpixel((0, 0))[3] == 0                 # coins arrondis transparents
        assert carre.getpixel((128, 128))[3] == 255
        b = logo.banniere()
        assert b.size[1] == 128 and b.size[0] > 256

    def test_couleurs_du_texte(self, logo):
        img = logo.carre()
        couleurs = {img.getpixel((x, y)) for x in range(0, 256, 2) for y in range(150, 230, 2)}   # zone du texte
        proche = lambda c, ref: all(abs(a - b) < 12 for a, b in zip(c[:3], ref[:3]))  # noqa: E731
        assert any(proche(c, logo.BLEU_LM) for c in couleurs)
        assert any(proche(c, logo.VIOLET_AGENT) for c in couleurs)

    def test_sans_les_logos_optionnels(self, logo, monkeypatch):
        vrai = logo.charger
        monkeypatch.setattr(logo, "charger", lambda nom, h: vrai(nom, h) if nom == "python.png" else None)
        assert logo.carre().size == (256, 256)          # badge de l'agent à la place

    def test_badge(self, logo):
        b = logo.badge(64)
        assert b.size == (64, 64) and b.getpixel((32, 32))[3] == 255
