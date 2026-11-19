"""Le modèle sur le NPU Intel de ce PC, servi par OpenVINO Model Server (OVMS) : même API que LM Studio (compatible
OpenAI) sur 127.0.0.1, sous l'adresse /v3. OVMS est lancé sans fenêtre et arrêté à la fin, seulement si c'est le
script qui l'a lancé (son numéro de processus est noté dans un fichier : le dernier passage d'une boucle, ou
l'annulation d'une routine depuis l'interface, l'arrête aussi)."""
import subprocess
import time
import urllib.request

import agent

PORT = 8771
NOM = "lmagent-npu"            # nom du modèle dans les requêtes envoyées à OVMS
ATTENTE_MAX_S = 900            # 1re fois : compilation du modèle pour le NPU (1 à 2 min ; plus sur un PC lent)


def url():
    return f"http://127.0.0.1:{PORT}/v3"


def _fichier_pid():
    return agent.npu_installation.dossier() / "ovms.pid"


def pret():
    """Le modèle est-il chargé et prêt à répondre ? (OVMS répond avant que le modèle soit prêt.)"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/v2/models/{NOM}/ready", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def demarrer():
    """URL du serveur NPU prêt, ou None (on passe au suivant). Installe OpenVINO la première fois si permis."""
    inst = agent.npu_installation
    if pret():
        return url()
    if not inst.installe():
        if not agent.CONFIG.get("npu_installation_auto", True):
            agent.say("   NPU présent mais OpenVINO pas installé (réglage « npu_installation_auto » coupé) : on passe au suivant")
            return None
        agent.say("   Première utilisation du NPU : installation d'OpenVINO et du modèle (une seule fois)")
        if not inst.installer(agent.say):
            return None
    agent.say(f"   Démarrage d'OpenVINO sur le NPU ({inst.modele()})...")
    journal = open(agent.LOGS / "ovms.log", "a", encoding="utf-8")
    proc = subprocess.Popen([str(inst.exe()), "--rest_port", str(PORT), "--rest_bind_address", "127.0.0.1",
                             "--model_path", str(inst.dossier_modele()), "--model_name", NOM],
                            stdout=journal, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _fichier_pid().write_text(str(proc.pid), encoding="ascii")
    debut = time.time()
    while time.time() - debut < ATTENTE_MAX_S:
        if pret():
            agent.say(f"   Modèle prêt sur le NPU en {time.time() - debut:.0f} s")
            return url()
        if proc.poll() is not None:
            agent.say(f"   ⚠️ OpenVINO s'est arrêté (code {proc.returncode}, détails dans logs/ovms.log)")
            _fichier_pid().unlink(missing_ok=True)
            return None
        time.sleep(2)
    agent.say(f"   ⚠️ Modèle toujours pas prêt sur le NPU après {ATTENTE_MAX_S} s : on passe au suivant")
    arreter()
    return None


def arreter():
    """Arrête OVMS s'il a été lancé par le script (numéro de processus noté). Renvoie True s'il a été arrêté."""
    f = _fichier_pid()
    try:
        pid = int(f.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    f.unlink(missing_ok=True)
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace")
    if "ovms.exe" not in r.stdout.lower():      # déjà arrêté (ou numéro repris par un autre programme)
        return False
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    agent.log("🧹 OpenVINO arrêté (NPU libéré)")
    print("🧹 OpenVINO arrêté (NPU libéré)")
    return True


def adapter(req_body):
    """Requête prévue pour LM Studio -> pour OVMS : nom du modèle, réflexion coupée à la façon de Qwen3."""
    req = dict(req_body, model=NOM)
    if req.pop("reasoning_effort", None) == "none":
        req["chat_template_kwargs"] = {"enable_thinking": False}
    return req
