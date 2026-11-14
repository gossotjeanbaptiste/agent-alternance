"""Boucle de passages (boucle.py) : modèle et LM Studio gardés ouverts jusqu'au dernier passage.
Tout est simulé : aucune commande LM Studio n'est lancée (déchargement et fermeture remplacés)."""
import pytest

import agent
import boucle
import lmagent


@pytest.fixture
def passage(monkeypatch):
    """Simule un passage : variables de boucle, déchargement / fermeture enregistrés au lieu d'être faits."""
    fait = {"dechargements": [], "fermetures": 0}

    def lms(*args, **k):
        if args[0] == "unload":
            fait["dechargements"].append(args[1])
        elif args[:2] == ("server", "stop"):
            fait["fermetures"] += 1
    monkeypatch.setattr(agent, "_lms", lms)
    monkeypatch.setattr(agent.subprocess, "run", lambda *a, **k: None)     # taskkill de LM Studio
    monkeypatch.setattr(agent, "A_DECHARGER", [])
    monkeypatch.setattr(agent, "LMSTUDIO_OUVERT_PAR_SCRIPT", False)

    def lancer(numero, total, charge=None, lmstudio_ouvert=False):
        """Un passage n° numero sur total : charge éventuellement le modèle, puis se termine (liberer_modele)."""
        for k, v in boucle.environnement("test", numero, total).items():
            monkeypatch.setenv(k, v)
        agent.A_DECHARGER.clear()
        agent.LMSTUDIO_OUVERT_PAR_SCRIPT = lmstudio_ouvert
        if charge:
            agent.A_DECHARGER.append(charge)
        agent.liberer_modele()
    fait["lancer"] = lancer
    yield fait
    boucle.nettoyer("test")


def test_seul_le_dernier_passage_referme(passage):
    passage["lancer"](1, 3, charge="qwen", lmstudio_ouvert=True)    # le 1er charge le modèle et ouvre LM Studio
    assert passage["dechargements"] == [] and passage["fermetures"] == 0
    passage["lancer"](2, 3)                                         # modèle déjà là : rien chargé
    assert passage["dechargements"] == [] and passage["fermetures"] == 0
    passage["lancer"](3, 3)                                         # le dernier referme ce que le 1er a ouvert
    assert passage["dechargements"] == ["qwen"] and passage["fermetures"] == 1
    assert not boucle.fichier().exists()


def test_sans_boucle_tout_est_referme(passage, monkeypatch):
    monkeypatch.delenv("LMAGENT_BOUCLE", raising=False)
    agent.A_DECHARGER.append("qwen")
    agent.LMSTUDIO_OUVERT_PAR_SCRIPT = True
    agent.liberer_modele()
    assert passage["dechargements"] == ["qwen"] and passage["fermetures"] == 1


def test_pas_de_double_dechargement(passage):
    passage["lancer"](1, 2, charge="qwen")
    passage["lancer"](2, 2, charge="qwen")           # même modèle noté deux fois
    assert passage["dechargements"] == ["qwen"]


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
