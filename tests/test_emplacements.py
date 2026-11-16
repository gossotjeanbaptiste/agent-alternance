"""Emplacements des fichiers personnels (emplacements.py), chemin du tableau (commun.py)
et option « utiliser une tour » (agent.py, tour_web.py). Aucune connexion à la tour n'est testée."""
import importlib
import sys
from pathlib import Path

import pytest

import agent
import commun
import emplacements


def recharger(monkeypatch, **env):
    """Recharge emplacements.py avec un environnement donné (sans toucher au module des autres tests)."""
    for k in ("LMAGENT_DOSSIER", "APPDATA"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("emplacements_test", emplacements.__file__)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestEmplacements:
    def test_depuis_le_code(self, monkeypatch):
        m = recharger(monkeypatch)
        assert m.DEPUIS_LE_CODE and m.BASE == m.SOURCE
        assert m.config_agent() == m.SOURCE / "config.json"
        assert m.donnees() == m.SOURCE / "alternance" / "donnees"
        assert m.dossier("logs") == m.SOURCE / "logs"

    def test_version_installee_dans_appdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        m = recharger(monkeypatch, APPDATA=str(tmp_path))
        assert m.INSTALLEE and not m.DEPUIS_LE_CODE
        assert m.BASE == tmp_path / "LMAgent"
        assert m.config_agent() == tmp_path / "LMAgent" / "config.json"
        assert m.donnees() == tmp_path / "LMAgent" / "donnees"
        assert m.dossier("linkedin") == tmp_path / "LMAgent" / "linkedin"

    def test_dossier_force(self, monkeypatch, tmp_path):
        m = recharger(monkeypatch, LMAGENT_DOSSIER=str(tmp_path))
        assert m.BASE == tmp_path and not m.DEPUIS_LE_CODE and m.donnees() == tmp_path / "donnees"

    def test_modeles_fournis_avec_l_appli(self):
        assert (emplacements.modeles() / "config_alternance.example.json").exists()
        assert (emplacements.modeles() / "interdits.example.md").exists()

    def test_les_tests_sont_isoles(self):
        assert not emplacements.DEPUIS_LE_CODE
        assert emplacements.BASE != emplacements.SOURCE
        assert agent.LOGS.parent != emplacements.SOURCE


class TestCheminTableau:
    def test_vide_dossier_de_donnees(self, cfg):
        cfg["tableau_suivi"] = ""
        assert commun.chemin_tableau() == commun.donnees.chemin("suivi_alternance.xlsx")
        cfg.pop("tableau_suivi")
        assert commun.chemin_tableau().name == "suivi_alternance.xlsx"

    def test_chemin_indique(self, cfg, tmp_path):
        cfg["tableau_suivi"] = str(tmp_path / "mon_suivi.xlsx")
        assert commun.chemin_tableau() == tmp_path / "mon_suivi.xlsx"
        cfg["tableau_suivi"] = "~/x.xlsx"
        assert commun.chemin_tableau() == Path.home() / "x.xlsx"

    def test_pieces_jointes(self, cfg, tmp_path, monkeypatch, capsys):
        """Seuls les fichiers qui existent sont joints ; un chemin cassé est cherché dans pieces_jointes/,
        un fichier introuvable est signalé (une fois)."""
        monkeypatch.setattr(commun, "_PJ_SIGNALEES", set())
        cfg["pieces_jointes"] = None
        assert commun.pieces_jointes() == []
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF")
        dossier = emplacements.dossier("pieces_jointes")
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "calendrier.pdf").write_bytes(b"%PDF")
        try:
            cfg["pieces_jointes"] = [str(cv), r"D:\autre_pc\calendrier.pdf", "introuvable.pdf"]
            assert commun.pieces_jointes() == [str(cv), str(dossier / "calendrier.pdf")]
            assert "introuvable.pdf" in capsys.readouterr().out
            commun.pieces_jointes()
            assert "introuvable.pdf" not in capsys.readouterr().out          # signalé une seule fois
        finally:
            (dossier / "calendrier.pdf").unlink()

    def test_config_d_exemple_sans_chemin_en_dur(self):
        import json
        ex = json.loads((emplacements.modeles() / "config_alternance.example.json").read_text(encoding="utf-8"))
        assert ex["tableau_suivi"] == "" and ex["pieces_jointes"] == []


class TestUtiliserTour:
    @pytest.mark.parametrize("config, attendu", [
        ({"utiliser_tour": True}, True),
        ({"utiliser_tour": False, "serveurs": [{"nom": "tour", "url": "http://t:1236/v1"}]}, False),
        ({"serveurs": [{"nom": "tour", "url": "http://t:1236/v1"}, {"nom": "ce PC", "url": "local"}]}, True),
        ({"serveurs": [{"nom": "ce PC", "url": "local"}]}, False),
        ({}, False),
    ])
    def test_reglage_ou_deduction(self, config, attendu):
        assert agent.utiliser_tour(config) is attendu

    def test_sans_tour_seul_ce_pc_est_essaye(self, monkeypatch):
        """ensure_server n'essaie ni de réveiller ni de joindre la tour quand elle n'est pas utilisée."""
        if not (Path(emplacements.SOURCE) / "tour.py").exists():
            pytest.skip("branche sans tour.py : ensure_server n'utilise que ce PC")
        monkeypatch.setitem(agent.CONFIG, "utiliser_tour", False)
        monkeypatch.setitem(agent.CONFIG, "serveurs", [{"nom": "tour", "url": "http://t:1236/v1", "reveil": True},
                                                       {"nom": "ce PC", "url": "local"}])
        monkeypatch.delenv("LMSTUDIO_URL", raising=False)
        essais = []
        monkeypatch.setattr(agent, "_reachable", lambda url: essais.append(url) or False)
        monkeypatch.setattr(agent, "_serveur_local", lambda: "http://localhost:1234/v1")
        agent.ensure_server()
        assert essais == [] and agent.SERVEUR == "ce PC"

    def test_page_tour_cachee_sans_tour(self, monkeypatch, client):
        monkeypatch.setitem(agent.CONFIG, "utiliser_tour", False)
        assert client.get("/tour").status_code == 404
        assert 'href="/tour"' not in client.get("/").get_data(as_text=True)
        assert client.get("/api/tour").status_code == 404

    def test_page_tour_affichee_avec_tour(self, monkeypatch, client):
        import tour_web
        if tour_web.tour is None:
            pytest.skip("branche sans tour.py")
        monkeypatch.setitem(agent.CONFIG, "utiliser_tour", True)
        assert 'href="/tour"' in client.get("/").get_data(as_text=True)

    def test_tour_py_sans_config(self, monkeypatch, tmp_path):
        """tour.py se charge même sans config.json (installation neuve)."""
        chemin = Path(emplacements.SOURCE) / "tour.py"
        if not chemin.exists():
            pytest.skip("branche sans tour.py")
        monkeypatch.setattr(emplacements, "config_agent", lambda: tmp_path / "absent.json")
        spec = importlib.util.spec_from_file_location("tour_test", chemin)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        assert m.T["port_serveur"] == 1235
