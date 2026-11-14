"""Boucle de passages (boucle.py) : modèle et LM Studio gardés ouverts jusqu'au dernier passage.
Tout est simulé : aucune requête vers LM Studio, la tour ou ce PC (déchargement et fermeture remplacés)."""
import sys
import types

import pytest

import agent
import boucle
import lmagent


@pytest.fixture
def passage(monkeypatch):
    """Simule un passage : variables de boucle, déchargement / fermeture enregistrés au lieu d'être faits."""
    fait = {"dechargements": [], "fermetures": 0, "veilles": 0}
    monkeypatch.setattr(agent, "_api", lambda base, m, chemin, corps=None, timeout=0:
                        fait["dechargements"].append(corps["instance_id"]))
    monkeypatch.setattr(agent, "fermer_lmstudio", lambda: fait.__setitem__("fermetures", fait["fermetures"] + 1))
    monkeypatch.setattr(agent, "remettre_tour_en_veille", lambda: fait.__setitem__("veilles", fait["veilles"] + 1))
    faux_tour = types.SimpleNamespace(LMSTUDIO_OUVERT_PAR_SCRIPT=False)
    monkeypatch.setitem(sys.modules, "tour", faux_tour)
    monkeypatch.setattr(agent, "A_DECHARGER", [])
    monkeypatch.setattr(agent, "TOUR_REVEILLEE", False)
    monkeypatch.setattr(agent, "LMSTUDIO_LOCAL_OUVERT_PAR_SCRIPT", False)

    def lancer(numero, total, charge=None, lmstudio_ouvert=False):
        """Un passage n° numero sur total : charge éventuellement le modèle, puis se termine (liberer_modele)."""
        for k, v in boucle.environnement("test", numero, total).items():
            monkeypatch.setenv(k, v)
        agent.A_DECHARGER.clear()
        faux_tour.LMSTUDIO_OUVERT_PAR_SCRIPT = lmstudio_ouvert
        if charge:
            agent.A_DECHARGER.append(("distant", "tour", "http://tour:1234", charge))
        agent.liberer_modele()
    fait["lancer"], fait["tour"] = lancer, faux_tour
    yield fait
    boucle.nettoyer("test")


def test_seul_le_dernier_passage_referme(passage):
    passage["lancer"](1, 3, charge="inst-1", lmstudio_ouvert=True)   # le 1er charge le modèle et ouvre LM Studio
    assert passage["dechargements"] == [] and passage["fermetures"] == 0 and passage["veilles"] == 0
    passage["lancer"](2, 3)                                         # modèle déjà là : rien chargé
    assert passage["dechargements"] == [] and passage["fermetures"] == 0
    passage["lancer"](3, 3)                                         # le dernier referme ce que le 1er a ouvert
    assert passage["dechargements"] == ["inst-1"] and passage["fermetures"] == 1 and passage["veilles"] == 1
    assert passage["tour"].LMSTUDIO_OUVERT_PAR_SCRIPT is True       # donc fermé par fermer_lmstudio
    assert not boucle.fichier().exists()


def test_sans_boucle_tout_est_referme(passage, monkeypatch):
    monkeypatch.delenv("LMAGENT_BOUCLE", raising=False)
    agent.A_DECHARGER.append(("distant", "tour", "http://tour:1234", "inst-1"))
    agent.liberer_modele()
    assert passage["dechargements"] == ["inst-1"] and passage["fermetures"] == 1


def test_pas_de_double_dechargement(passage):
    passage["lancer"](1, 2, charge="inst-1")
    passage["lancer"](2, 2, charge="inst-1")         # même instance notée deux fois
    assert passage["dechargements"] == ["inst-1"]


def test_tour_reveillee_par_un_passage_precedent(passage, monkeypatch):
    for k, v in boucle.environnement("test", 1, 2).items():
        monkeypatch.setenv(k, v)
    agent.TOUR_REVEILLEE = True
    agent.liberer_modele()
    agent.TOUR_REVEILLEE = False
    for k, v in boucle.environnement("test", 2, 2).items():
        monkeypatch.setenv(k, v)
    agent.liberer_modele()
    assert agent.TOUR_REVEILLEE is True and passage["veilles"] == 1


def test_fichier_d_etat_illisible(passage, monkeypatch):
    for k, v in boucle.environnement("test", 2, 2).items():
        monkeypatch.setenv(k, v)
    boucle.fichier().parent.mkdir(parents=True, exist_ok=True)
    boucle.fichier().write_text("pas du json", encoding="utf-8")
    assert boucle.reprendre() == {} and not boucle.fichier().exists()


@pytest.mark.parametrize("passage_n, total, attendu", [(1, 3, "1"), (2, 3, "1"), (3, 3, "0"), (1, 1, "0")])
def test_environnement(passage_n, total, attendu):
    env = boucle.environnement(42, passage_n, total)
    assert env["LMAGENT_BOUCLE"] == "42" and env["LMAGENT_GARDER_OUVERT"] == attendu


def test_la_boucle_transmet_l_etat_et_nettoie(monkeypatch):
    envs = []
    monkeypatch.setattr(lmagent.subprocess, "call", lambda cmd, env=None, **k: envs.append(env) or 0)
    lmagent.routine(["--routine", "recherche", "--fois", "3"])
    assert [e["LMAGENT_GARDER_OUVERT"] for e in envs] == ["1", "1", "0"]
    assert len({e["LMAGENT_BOUCLE"] for e in envs}) == 1
    ident = envs[0]["LMAGENT_BOUCLE"]
    monkeypatch.setenv("LMAGENT_BOUCLE", ident)
    assert not boucle.fichier().exists()
