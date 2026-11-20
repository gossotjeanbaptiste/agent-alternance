"""Tour remise en veille quand l'utilisateur quitte LMAgent (web/src/veille_tour.py), jamais pour une mise à jour.
La tour est simulée (faux module tour) : rien n'est envoyé par SSH."""
import json
import sys
import types

import pytest

import emplacements
import icone_tache
import routines
import veille_tour


@pytest.fixture
def config(monkeypatch, tmp_path):
    """config.json de test : tour utilisée, mise en veille en quittant réglable."""
    f = tmp_path / "config.json"

    def ecrire(**tour):
        f.write_text(json.dumps({"utiliser_tour": True, "tour": tour}), encoding="utf-8")
    monkeypatch.setattr(emplacements, "config_agent", lambda: f)
    ecrire()
    return ecrire


@pytest.fixture
def tour(monkeypatch, config):
    """Faux module tour : joignable, carte libre ; les mises en veille demandées sont notées."""
    t = types.SimpleNamespace(joignable=True, occupee=False, veilles=[])
    t.ssh_ok = lambda: t.joignable
    t.ssh_lan_ok = lambda: False
    t.gpu_occupe = lambda log=print: t.occupee
    t.veille = lambda log=print: t.veilles.append(1) or True
    monkeypatch.setitem(sys.modules, "tour", t)
    monkeypatch.setattr(routines, "en_cours", lambda: False)
    return t


def test_quitter_met_la_tour_en_veille(tour):
    dit = []
    assert veille_tour.en_quittant(journal=dit.append) is True and tour.veilles == [1]
    assert any("mise en veille" in d for d in dit)


@pytest.mark.parametrize("cas", ["routine", "injoignable", "occupee", "reglage", "sans_tour"])
def test_tour_laissee_allumee(tour, config, monkeypatch, cas):
    if cas == "routine":
        monkeypatch.setattr(routines, "en_cours", lambda: True)
    elif cas == "injoignable":
        tour.joignable = False
    elif cas == "occupee":
        tour.occupee = True
    elif cas == "reglage":
        config(veille_en_quittant=False)
    else:
        emplacements.config_agent().write_text(json.dumps({"utiliser_tour": False}), encoding="utf-8")
    assert veille_tour.en_quittant(journal=lambda m: None) is False and tour.veilles == []


def test_branche_sans_tour(config, monkeypatch):
    monkeypatch.setitem(sys.modules, "tour", None)             # import tour -> ImportError
    assert veille_tour.en_quittant(journal=lambda m: None) is False


def test_erreur_ssh_sans_planter(tour):
    def coupe():
        raise OSError("connexion refusée")
    tour.ssh_ok = coupe
    assert veille_tour.en_quittant(journal=lambda m: None) is False


@pytest.mark.parametrize("par_l_utilisateur, veille", [(True, [1]), (False, [])])
def test_mise_a_jour_ne_met_pas_en_veille(monkeypatch, par_l_utilisateur, veille):
    """Fermeture pour une mise à jour automatique (par défaut) : pas de mise en veille."""
    vu, fermes = [], []
    monkeypatch.setattr(veille_tour, "en_quittant", lambda: vu.append(1))
    monkeypatch.setattr(icone_tache.os, "_exit", fermes.append)
    icone_tache.quitter(par_l_utilisateur=par_l_utilisateur)
    assert vu == veille and fermes == [0]
    vu.clear()
    icone_tache.quitter()
    assert vu == []
