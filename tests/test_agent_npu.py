"""Le modèle sur le NPU Intel par OpenVINO Model Server (src/agent/npu.py, npu_installation.py) et la bascule d'un
serveur à l'autre (post_chat). OVMS, le réseau et les processus sont simulés."""
import json
import os
import urllib.error
from types import SimpleNamespace

import pytest

import agent
import emplacements
from agent import npu, npu_installation as inst

GRAPHE = """input_stream: "HTTP_REQUEST_PAYLOAD:input"
    node_options: {
        [type.googleapis.com / mediapipe.LLMCalculatorOptions]: {
            max_num_seqs:256,
            device: "GPU",
            models_path: "./",
            plugin_config: '{"MAX_PROMPT_LEN":1024}',
            enable_prefix_caching: true,
        }
    }
"""


@pytest.fixture
def modele(monkeypatch):
    """Modèle NPU « installé » dans le dossier de test."""
    monkeypatch.setitem(agent.CONFIG, "modele_npu", "OpenVINO/Essai-int4-cw-ov")
    d = inst.dossier_modele()
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.pbtxt").write_text(GRAPHE, encoding="utf-8")
    inst.exe().parent.mkdir(parents=True, exist_ok=True)
    inst.exe().write_bytes(b"")
    return d


def test_gros_fichiers_dans_le_dossier_de_test():
    assert str(inst.dossier()).startswith(os.environ["LMAGENT_DOSSIER"])
    assert emplacements.gros_fichiers("openvino") == inst.dossier()


def test_graphe_regle_pour_le_npu(modele):
    inst.regler_graphe()
    inst.regler_graphe()                                   # deux fois : toujours un seul réglage
    texte = (modele / "graph.pbtxt").read_text(encoding="utf-8")
    assert texte.count('device: "NPU"') == 1 and 'device: "GPU"' not in texte
    conf = json.loads(texte.split("plugin_config: '")[1].split("'")[0])
    assert conf["MAX_PROMPT_LEN"] == inst.CONSIGNE_MAX and conf["MIN_RESPONSE_LEN"] == inst.REPONSE_MIN
    assert conf["DEVICE_PROPERTIES"]["NPU"]["NPUW_LLM_ENABLE_PREFIX_CACHING"] is True
    assert texte.count("plugin_config") == 1 and inst.installe()


def test_pas_installe_et_installation_coupee(monkeypatch):
    monkeypatch.setitem(agent.CONFIG, "modele_npu", "OpenVINO/Absent-ov")
    monkeypatch.setitem(agent.CONFIG, "npu_installation_auto", False)
    monkeypatch.setattr(npu, "pret", lambda: False)
    monkeypatch.setattr(agent, "say", lambda m: None)
    monkeypatch.setattr(inst, "installer", lambda log: pytest.fail("rien ne doit être téléchargé"))
    assert npu.demarrer() is None


class FauxProcessus:
    def __init__(self, fin=None):
        self.pid, self.returncode, self._fin = 4321, fin, fin

    def poll(self):
        return self._fin


@pytest.fixture
def lancement(monkeypatch, modele):
    vu = {"lances": [], "pret": [False, False, True]}
    monkeypatch.setattr(npu, "pret", lambda: vu["pret"].pop(0) if vu["pret"] else True)
    monkeypatch.setattr(npu.time, "sleep", lambda s: None)
    monkeypatch.setattr(agent, "say", lambda m: vu.setdefault("dit", []).append(m))
    monkeypatch.setattr(npu.subprocess, "Popen", lambda args, **k: vu["lances"].append((args, k)) or vu["proc"])
    vu["proc"] = FauxProcessus()
    return vu


def test_demarrage_sans_fenetre_sur_127_0_0_1(lancement):
    assert npu.demarrer() == npu.url()
    args, options = lancement["lances"][0]
    assert args[args.index("--rest_bind_address") + 1] == "127.0.0.1"
    assert args[args.index("--model_name") + 1] == npu.NOM
    assert options["creationflags"] == getattr(npu.subprocess, "CREATE_NO_WINDOW", 0)
    assert npu._fichier_pid().read_text(encoding="ascii") == "4321"


def test_ovms_qui_s_arrete_on_passe_au_suivant(lancement):
    lancement["proc"], lancement["pret"] = FauxProcessus(fin=1), [False] * 5
    assert npu.demarrer() is None and not npu._fichier_pid().exists()


def test_deja_pret_rien_n_est_lance(lancement):
    lancement["pret"] = [True]
    assert npu.demarrer() == npu.url() and lancement["lances"] == []


def test_arret_seulement_du_processus_lance(monkeypatch, modele):
    tues = []
    monkeypatch.setattr(npu.subprocess, "run", lambda args, **k: tues.append(args) if args[0] == "taskkill"
                        else SimpleNamespace(stdout="ovms.exe   4321 Console", returncode=0))
    assert npu.arreter() is False and tues == []           # rien de lancé par le script
    npu._fichier_pid().write_text("4321", encoding="ascii")
    assert npu.arreter() is True and tues == [["taskkill", "/PID", "4321", "/F"]]
    assert not npu._fichier_pid().exists()


def test_numero_repris_par_un_autre_programme(monkeypatch, modele):
    monkeypatch.setattr(npu.subprocess, "run", lambda args, **k: pytest.fail("rien à tuer") if args[0] == "taskkill"
                        else SimpleNamespace(stdout="Info : aucune tâche", returncode=0))
    npu._fichier_pid().write_text("4321", encoding="ascii")
    assert npu.arreter() is False


def test_requete_adaptee_pour_openvino():
    req = npu.adapter({"model": "qwen/qwen3.5-9b", "reasoning_effort": "none", "messages": []})
    assert req["model"] == npu.NOM and "reasoning_effort" not in req
    assert req["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in npu.adapter({"model": "x", "messages": []})


@pytest.fixture
def requetes(monkeypatch):
    """post_chat avec un serveur qui lâche : la bascule ne réessaie pas les serveurs déjà lâchés."""
    vu = {"corps": [], "bascules": []}

    class Reponse:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=0):
        vu["corps"].append(json.loads(req.data))
        if len(vu["corps"]) == 1:
            raise urllib.error.URLError("connexion coupée")
        return Reponse(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
    monkeypatch.setattr(agent.serveur.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(agent, "ECARTES", ["tour"] if hasattr(agent, "_charger_distant") else [])
    monkeypatch.setattr(agent, "SERVEUR", "ce PC (NPU Intel)")
    monkeypatch.setattr(agent, "BASE_URL", "http://127.0.0.1:8771/v3")
    monkeypatch.setattr(agent, "MOTEUR", "openvino")
    monkeypatch.setattr(agent, "say", lambda m: None)
    monkeypatch.setattr(npu, "arreter", lambda: vu.setdefault("arrete", True))

    def bascule(sauf=()):
        vu["bascules"].append(sauf)
        agent.SERVEUR, agent.MOTEUR = "ce PC (carte graphique du processeur)", "lmstudio"
    monkeypatch.setattr(agent, "ensure_server", bascule)
    return vu


def test_bascule_du_npu_vers_le_suivant(requetes):
    assert agent.post_chat({"model": "qwen/qwen3.5-9b", "reasoning_effort": "none", "messages": []})["content"] == "ok"
    assert requetes["corps"][0]["model"] == npu.NOM                    # 1er essai : adapté pour OpenVINO
    assert requetes["corps"][1]["model"] == "qwen/qwen3.5-9b"           # 2e : LM Studio, requête d'origine
    assert requetes["arrete"] is True                                  # NPU libéré
    assert "ce PC (NPU Intel)" in requetes["bascules"][0]
