"""Ce PC fait tourner le modèle, dans l'ordre : carte dédiée, NPU Intel (OpenVINO), carte du processeur, processeur
(src/agent/materiel.py, local.py). LM Studio, PowerShell et OVMS sont simulés."""
import subprocess
from types import SimpleNamespace

import pytest

import agent
from agent import local, materiel


@pytest.mark.parametrize("nom, dediee, integree", [
    ("NVIDIA GeForce RTX 4060 Laptop GPU", True, False),
    ("NVIDIA GeForce GTX 1650", True, False),
    ("AMD Radeon RX 7800 XT", True, False),
    ("AMD Radeon RX6600", True, False),
    ("AMD Radeon Pro W7600", True, False),
    ("AMD Radeon(TM) Graphics", False, True),
    ("AMD Radeon 780M Graphics", False, True),
    ("Intel(R) Arc(TM) A770 Graphics", True, False),
    ("Intel(R) Arc(TM) B580 Graphics", True, False),
    ("Intel(R) Arc(TM) Pro A60 Graphics", True, False),
    ("Intel(R) Arc(TM) Graphics", False, True),          # Core Ultra (Meteor Lake) : intégrée malgré « Arc »
    ("Intel(R) Arc(TM) 140V GPU (16GB)", False, True),   # Lunar Lake : intégrée
    ("Intel(R) Iris(R) Xe Graphics", False, True),
    ("Intel(R) UHD Graphics 620", False, True),
    ("Microsoft Basic Display Adapter", False, False),
    ("Parsec Virtual Display Adapter", False, False),
])
def test_carte_dediee_ou_integree(nom, dediee, integree):
    assert materiel.est_dediee(nom) is dediee
    assert materiel.est_integree(nom) is integree


@pytest.fixture
def pc(monkeypatch):
    """PC simulé : cartes graphiques et NPU réglables."""
    etat = {"cartes": [], "npu": ""}
    monkeypatch.setattr(agent, "cartes_graphiques", lambda: etat["cartes"])
    monkeypatch.setattr(agent, "npu_intel", lambda: etat["npu"])
    monkeypatch.setitem(agent.CONFIG, "ordre_ce_pc", None)
    return etat


def test_portable_core_ultra_npu_avant_la_carte_du_processeur(pc):
    pc["cartes"], pc["npu"] = ["Intel(R) Arc(TM) Graphics"], "Intel(R) AI Boost"
    assert [n for n, _ in local.niveaux()] == ["npu", "carte_integree", "processeur"]


def test_pc_avec_carte_dediee_en_premier(pc):
    pc["cartes"] = ["Intel(R) UHD Graphics 770", "NVIDIA GeForce RTX 4070"]
    niveaux = local.niveaux()
    assert [n for n, _ in niveaux] == ["carte_dediee", "carte_integree", "processeur"]
    assert niveaux[0][1] == "ce PC (carte graphique NVIDIA GeForce RTX 4070)"
    assert local.famille("carte_dediee") == "cuda"


def test_carte_amd_dediee_en_vulkan(pc):
    pc["cartes"] = ["AMD Radeon RX 7800 XT"]
    assert local.famille("carte_dediee") == "vulkan" and local.famille("processeur") == "cpu"


def test_pc_sans_carte_ni_npu_processeur_seul(pc):
    pc["cartes"] = ["Microsoft Basic Display Adapter"]
    assert local.niveaux() == [("processeur", "ce PC (processeur)")]


def test_ordre_regle_et_niveau_inconnu(pc, monkeypatch):
    pc["cartes"], pc["npu"] = ["Intel(R) Arc(TM) Graphics"], "Intel(R) AI Boost"
    dit = []
    monkeypatch.setattr(agent, "say", dit.append)
    monkeypatch.setitem(agent.CONFIG, "ordre_ce_pc", ["carte_integree", "gpu_magique", "npu"])
    assert [n for n, _ in local.niveaux()] == ["carte_integree", "npu"]
    assert any("gpu_magique" in d for d in dit)


@pytest.fixture
def lms(monkeypatch, pc):
    """LM Studio simulé : commandes lms notées, chargement réussi ou non."""
    vu = {"appels": [], "charge": False, "echec": False, "moteur": True}

    def faux(*args, timeout=0):
        vu["appels"].append(args)
        if args[0] == "load":
            vu["charge"] = not vu["echec"]
            return SimpleNamespace(returncode=1 if vu["echec"] else 0, stdout="", stderr="Not enough memory")
        sortie = agent.CONFIG["modele"] if args[0] == "ps" and vu["charge"] else ""
        return SimpleNamespace(returncode=0, stdout=sortie, stderr="")
    monkeypatch.setattr(agent, "_lms", faux)
    monkeypatch.setattr(agent, "_lmstudio_demarre", lambda: "http://localhost:1234/v1")
    monkeypatch.setattr(agent, "choisir_moteur", lambda famille: vu.setdefault("familles", []).append(famille)
                        or vu["moteur"])
    monkeypatch.setattr(agent, "A_DECHARGER", [])
    monkeypatch.setattr(agent, "MOTEUR", "lmstudio")
    monkeypatch.setattr(agent, "say", lambda m: None)
    return vu


def test_processeur_charge_sans_carte_graphique(lms):
    assert local.demarrer("processeur") == "http://localhost:1234/v1"
    charge = next(a for a in lms["appels"] if a[0] == "load")
    assert charge[charge.index("--gpu") + 1] == "off" and lms["familles"] == ["cpu"]
    assert agent.MOTEUR == "lmstudio" and agent.A_DECHARGER == [agent.a_decharger_local()]


def test_carte_du_processeur_tout_sur_la_carte(lms):
    local.demarrer("carte_integree")
    charge = next(a for a in lms["appels"] if a[0] == "load")
    assert charge[charge.index("--gpu") + 1] == "max" and lms["familles"] == ["vulkan"]


def test_chargement_impossible_on_passe_au_suivant(lms):
    lms["echec"] = True
    assert local.demarrer("carte_integree") is None and agent.A_DECHARGER == []


def test_moteur_manquant_on_passe_au_suivant(lms):
    lms["moteur"] = False
    assert local.demarrer("carte_integree") is None
    assert not any(a[0] == "load" for a in lms["appels"])


def test_modele_deja_charge_garde_tel_quel(lms):
    lms["charge"] = True
    assert local.demarrer("carte_integree") == "http://localhost:1234/v1"
    assert not any(a[0] == "load" for a in lms["appels"]) and agent.A_DECHARGER == []


def test_npu_passe_par_openvino(monkeypatch):
    monkeypatch.setattr(agent, "MOTEUR", "lmstudio")      # remis tel quel après le test
    monkeypatch.setattr(agent.npu, "demarrer", lambda: "http://127.0.0.1:8771/v3")
    assert local.demarrer("npu") == "http://127.0.0.1:8771/v3" and agent.MOTEUR == "openvino"


def test_npu_intel_lu_par_powershell(monkeypatch):
    monkeypatch.setattr(materiel.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout="Intel(R) AI Boost\r\n", returncode=0))
    assert materiel.npu_intel() == "Intel(R) AI Boost"
    monkeypatch.setattr(materiel.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("powershell", 60)))
    assert materiel.npu_intel() == ""


def test_niveaux_dans_l_ordre_et_bascule_sans_revenir_en_arriere(monkeypatch):
    """Les deux branches : premier niveau qui marche gardé ; après une bascule, les niveaux lâchés sont sautés."""
    monkeypatch.setitem(agent.CONFIG, "utiliser_tour", False)
    monkeypatch.setitem(agent.CONFIG, "serveurs", [{"nom": "ce PC", "url": "local"}])
    monkeypatch.delenv("LMSTUDIO_URL", raising=False)
    monkeypatch.setattr(agent, "SERVEUR", "?")
    monkeypatch.setattr(agent, "BASE_URL", None)
    monkeypatch.setattr(agent, "say", lambda m: None)
    niveaux = [("npu", "ce PC (NPU Intel)"), ("carte_integree", "ce PC (carte graphique du processeur)"),
               ("processeur", "ce PC (processeur)")]
    monkeypatch.setattr(agent, "niveaux_locaux", lambda: niveaux)
    essais = []
    monkeypatch.setattr(agent, "demarrer_local", lambda n: essais.append(n) or f"http://{n}/v1")
    agent.ensure_server()
    assert essais == ["npu"] and agent.SERVEUR == "ce PC (NPU Intel)"
    agent.ensure_server(sauf=("ce PC (NPU Intel)",))
    assert essais == ["npu", "carte_integree"] and agent.BASE_URL == "http://carte_integree/v1"
