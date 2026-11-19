"""Chargement du modèle sur la tour (src/agent/serveur.py, branche main) : API REST de LM Studio simulée."""
import http.client

import pytest

import agent

serveur = pytest.importorskip("agent.serveur")
if not hasattr(serveur, "_charger_distant"):
    pytest.skip("branche sans tour", allow_module_level=True)


@pytest.fixture
def api(monkeypatch):
    """Faux LM Studio distant : les réponses préparées sont rendues dans l'ordre (une exception est levée)."""
    vu = {"appels": [], "reponses": []}

    def faux(base, methode, chemin, corps=None, timeout=0):
        vu["appels"].append((methode, chemin))
        r = vu["reponses"].pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(agent, "_api", faux)
    monkeypatch.setattr(serveur.time, "sleep", lambda s: vu.setdefault("attentes", []).append(s))
    monkeypatch.setattr(agent, "A_DECHARGER", [])
    monkeypatch.setitem(agent.CONFIG, "modele", "qwen/qwen3.5-9b")
    return vu


def test_lmstudio_pas_encore_pret_reessaye(api):
    """LM Studio qui vient de s'ouvrir coupe la connexion : nouvel essai, puis modèle chargé et noté à décharger."""
    api["reponses"] = [{"models": []}, http.client.RemoteDisconnected("Remote end closed connection without response"),
                       {"models": []}, {"instance_id": "inst-1"}]
    serveur._charger_distant("tour", "http://tour:1236/v1")
    assert agent.A_DECHARGER == [("distant", "tour", "http://tour:1236", "inst-1")]
    assert api["attentes"] == [serveur.ATTENTE_CHARGEMENT_S]


def test_abandon_apres_plusieurs_essais(api):
    api["reponses"] = [ConnectionResetError("coupé")] * serveur.ESSAIS_CHARGEMENT
    serveur._charger_distant("tour", "http://tour:1236/v1")
    assert agent.A_DECHARGER == [] and len(api["appels"]) == serveur.ESSAIS_CHARGEMENT


def test_modele_deja_charge(api):
    api["reponses"] = [{"models": [{"key": "qwen/qwen3.5-9b", "loaded_instances": [{"id": "deja"}]}]}]
    serveur._charger_distant("tour", "http://tour:1236/v1")
    assert agent.A_DECHARGER == [("distant", "tour", "http://tour:1236", "deja")] and "attentes" not in api


def test_tour_injoignable_puis_niveaux_de_ce_pc_dans_l_ordre(monkeypatch):
    """La tour ne répond pas : niveaux de ce PC dans l'ordre, le premier qui marche est gardé ; ils ne sont
    cherchés qu'une fois la tour écartée."""
    monkeypatch.setitem(agent.CONFIG, "utiliser_tour", True)
    monkeypatch.setitem(agent.CONFIG, "serveurs", [{"nom": "tour", "url": "http://tour:1236/v1"},
                                                   {"nom": "ce PC", "url": "local"}])
    monkeypatch.delenv("LMSTUDIO_URL", raising=False)
    monkeypatch.setattr(agent, "SERVEUR", "?")
    monkeypatch.setattr(agent, "BASE_URL", None)
    ordre = []
    monkeypatch.setattr(agent, "_reachable", lambda url: ordre.append("tour") or False)
    monkeypatch.setattr(agent, "niveaux_locaux", lambda: ordre.append("détection") or [
        ("npu", "ce PC (NPU Intel)"), ("carte_integree", "ce PC (carte graphique du processeur)")])
    monkeypatch.setattr(agent, "demarrer_local", lambda n: ordre.append(n) or (None if n == "npu" else "http://l/v1"))
    monkeypatch.setattr(agent, "say", lambda m: None)
    agent.ensure_server()
    assert ordre[-3:] == ["détection", "npu", "carte_integree"] and set(ordre[:-3]) == {"tour"}
    assert agent.SERVEUR == "ce PC (carte graphique du processeur)" and agent.BASE_URL == "http://l/v1"
