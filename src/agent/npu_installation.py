"""Installation de ce qu'il faut pour le NPU Intel : OpenVINO Model Server (OVMS, ~110 Mo, empreinte SHA-256 vérifiée)
et le modèle au format NPU (~5 Go, réglage « modele_npu »), dans %LOCALAPPDATA%\\LMAgent\\openvino.
Faite une fois, la première fois que le NPU sert (réglage « npu_installation_auto »)."""
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile

import agent
import emplacements

VERSION_OVMS = "2026.4.1"
URL_OVMS = (f"https://github.com/openvinotoolkit/model_server/releases/download/v{VERSION_OVMS}/"
            f"ovms_windows_{VERSION_OVMS}_python_off.zip")
MODELE_NPU = "OpenVINO/Qwen3-8B-int4-cw-ov"
# Le NPU travaille avec des tailles fixées à la compilation : consigne max (jetons) et réponse min réservée.
CONSIGNE_MAX = 4096
REPONSE_MIN = 1024


def dossier():
    return emplacements.gros_fichiers("openvino")


def exe():
    return dossier() / "ovms" / "ovms.exe"


def modele():
    return agent.CONFIG.get("modele_npu") or MODELE_NPU


def dossier_modele():
    return dossier() / "modeles" / modele()


def installe():
    """OVMS et le modèle sont-ils là (graphe compris) ?"""
    return exe().exists() and (dossier_modele() / "graph.pbtxt").exists()


def _telecharger(url, cible, log):
    """Télécharge url dans cible ; renvoie son empreinte SHA-256. Journal tous les 10 %."""
    h, recu, palier = hashlib.sha256(), 0, 0
    with urllib.request.urlopen(url, timeout=60) as r, open(cible, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        while bloc := r.read(1 << 20):
            f.write(bloc)
            h.update(bloc)
            recu += len(bloc)
            if total and recu * 10 // total > palier:
                palier = recu * 10 // total
                log(f"   … {palier * 10} % ({recu >> 20} Mo)")
    return h.hexdigest()


def installer_ovms(log):
    """OVMS téléchargé, vérifié (empreinte publiée à côté) et décompressé."""
    d = dossier()
    d.mkdir(parents=True, exist_ok=True)
    zip_ = d / "ovms.zip"
    log(f"   Téléchargement d'OpenVINO Model Server {VERSION_OVMS}...")
    with urllib.request.urlopen(URL_OVMS + ".sha256", timeout=60) as r:
        attendu = r.read().decode("ascii", "replace").split()[0].lower()
    if _telecharger(URL_OVMS, zip_, log) != attendu:
        zip_.unlink(missing_ok=True)
        raise RuntimeError("empreinte d'OVMS différente de celle publiée : téléchargement abandonné")
    tmp = d / "ovms_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_) as z:
        z.extractall(tmp)
    shutil.rmtree(d / "ovms", ignore_errors=True)
    (tmp / "ovms").rename(d / "ovms")
    shutil.rmtree(tmp, ignore_errors=True)
    zip_.unlink(missing_ok=True)


def installer_modele(log):
    """Modèle téléchargé par OVMS lui-même (Hugging Face), graphe préparé pour le NPU."""
    log(f"   Téléchargement du modèle {modele()} pour le NPU (~5 Go)...")
    r = subprocess.run([str(exe()), "--pull", "--source_model", modele(), "--model_repository_path",
                        str(dossier() / "modeles"), "--target_device", "NPU", "--task", "text_generation",
                        "--tool_parser", "hermes3", "--reasoning_parser", "qwen3"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200)
    if r.returncode or not (dossier_modele() / "graph.pbtxt").exists():
        raise RuntimeError(f"téléchargement du modèle impossible : {(r.stderr or r.stdout).strip()[-300:]}")
    regler_graphe()


def regler_graphe():
    """Graphe du modèle réglé pour le NPU : appareil, tailles fixes, cache de compilation (démarrages suivants
    en quelques secondes) et cache du début des consignes (le profil, commun à toutes les lettres)."""
    g = dossier_modele() / "graph.pbtxt"
    texte = g.read_text(encoding="utf-8-sig")
    texte = re.sub(r'\n\s*device: "[A-Z]+",', "", texte)
    texte = re.sub(r"\n\s*plugin_config: '[^']*',", "", texte)
    conf = {"MAX_PROMPT_LEN": CONSIGNE_MAX, "MIN_RESPONSE_LEN": REPONSE_MIN,
            "CACHE_DIR": (dossier() / "cache").as_posix(),
            "DEVICE_PROPERTIES": {"NPU": {"NPUW_LLM_ENABLE_PREFIX_CACHING": True}}}
    ajout = f'\n            device: "NPU",\n            plugin_config: \'{json.dumps(conf)}\','
    texte, n = re.subn(r"(max_num_seqs:\s*\d+,)", lambda m: m.group(1) + ajout, texte, count=1)
    if not n:
        raise RuntimeError("graphe du modèle inattendu (max_num_seqs absent)")
    g.write_text(texte, encoding="utf-8")


def installer(log=None):
    """Installe ce qui manque. Renvoie True si tout est prêt."""
    log = log or agent.say
    try:
        if not exe().exists():
            installer_ovms(log)
        if not (dossier_modele() / "graph.pbtxt").exists():
            installer_modele(log)
        log("   ✅ OpenVINO et le modèle NPU installés")
        return True
    except Exception as e:
        log(f"   ⚠️ Installation pour le NPU impossible : {e}")
        return False
