"""Icône de la zone de notification (web/src/icone_tache.py) : pystray simulé, aucune icône réelle affichée."""
import sys
import types

import pytest

import emplacements
import icone_tache


@pytest.fixture
def faux_pystray(monkeypatch):
    vu = {"stop": 0, "run": 0}

    class MenuItem:
        def __init__(self, texte, action, default=False):
            self.texte, self.action, self.default = texte, action, default

    class Icon:
        def __init__(self, nom, image, titre, menu):
            vu.update(nom=nom, image=image, titre=titre, menu=menu)
            self._visible = True

        @property
        def visible(self):
            return self._visible

        @visible.setter
        def visible(self, v):
            vu.setdefault("ordre", []).append("cachée")
            self._visible = v

        def run(self):
            vu["run"] += 1

        def stop(self):
            vu.setdefault("ordre", []).append("arrêtée")
            vu["stop"] += 1

    mod = types.ModuleType("pystray")
    mod.Menu, mod.MenuItem, mod.Icon = (lambda *items: list(items)), MenuItem, Icon
    monkeypatch.setitem(sys.modules, "pystray", mod)
    monkeypatch.setattr(icone_tache.threading, "Thread", lambda target, daemon: types.SimpleNamespace(start=target))
    yield vu
    icone_tache.ICONE["objet"] = None


LOGO = emplacements.RESSOURCES / "web" / "static" / "logo.png"


def test_menu_ouvrir_et_quitter(faux_pystray, monkeypatch):
    ouverts, fermes = [], []
    monkeypatch.setattr(icone_tache.webbrowser, "open", ouverts.append)
    monkeypatch.setattr(icone_tache.os, "_exit", fermes.append)
    import veille_tour
    veilles = []
    monkeypatch.setattr(veille_tour, "en_quittant", lambda: veilles.append(1))
    monkeypatch.setattr(veille_tour, "ARRET", {"lignes": [], "fini": False})
    monkeypatch.setattr("time.sleep", lambda s: None)
    icone = icone_tache.demarrer("http://127.0.0.1:8765", LOGO)
    assert icone is icone_tache.ICONE["objet"] and faux_pystray["run"] == 1
    assert faux_pystray["titre"] == "LMAgent"
    ouvrir, quitter = faux_pystray["menu"]
    assert ouvrir.default and "Ouvrir" in ouvrir.texte and "Quitter" in quitter.texte
    ouvrir.action()
    assert ouverts == ["http://127.0.0.1:8765"]
    quitter.action()
    assert fermes == [0] and faux_pystray["stop"] == 1 and icone_tache.ICONE["objet"] is None
    assert veilles == [1]                                       # « Quitter LMAgent » : tour remise en veille
    assert faux_pystray["ordre"] == ["cachée", "arrêtée"]      # retirée AVANT la fermeture du processus
    assert icone.visible is False


def test_sans_pystray(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)   # import impossible
    messages = []
    assert icone_tache.demarrer("http://x", LOGO, journal=messages.append) is None
    assert "pystray" in messages[0]


def test_arreter_sans_icone_et_deux_fois(faux_pystray):
    icone_tache.arreter()                                # rien à arrêter : pas d'erreur
    icone_tache.demarrer("http://x", LOGO)
    icone_tache.arreter()
    icone_tache.arreter()
    assert faux_pystray["stop"] == 1


def test_quitter_depuis_l_interface_retire_l_icone(client, faux_pystray, monkeypatch):
    lances = []
    monkeypatch.setattr("api.threading.Timer", lambda d, f, kwargs=None: types.SimpleNamespace(
        start=lambda: lances.append((f, kwargs))))
    assert client.post("/api/quitter", json={}).get_json()["ok"]
    assert lances == [(icone_tache.quitter, {"par_l_utilisateur": True})]     # bouton ⏻ : tour remise en veille
