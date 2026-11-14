"""
Agent IA local — LM Studio + Qwen3.5 9B
Aucune dépendance externe (bibliothèque standard Python uniquement).

Modes :
    python agent.py                    -> chat interactif (demande avant chaque action)
    python agent.py --tache trier      -> exécute taches/trier.txt sans intervention
    python agent.py --task "consigne"  -> exécute une consigne sans intervention

Réglages : config.json   |   Journal : logs/   |   Fichiers "supprimés" : corbeille/
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import emplacements  # noqa: E402  (où vivent config, journaux… : dossier du projet ou %APPDATA%\LMAgent)

ROOT = Path(__file__).parent.resolve()
WORKSPACE = emplacements.dossier("workspace")
CORBEILLE = emplacements.dossier("corbeille")
LOGS = emplacements.dossier("logs")
TACHES = emplacements.dossier("taches")
for d in (WORKSPACE, CORBEILLE, LOGS, TACHES):
    d.mkdir(parents=True, exist_ok=True)

CONFIG = {
    "modele": "qwen/qwen3.5-9b",
    "contexte": 16384,
    "dossiers_autorises": [],
    "powershell_en_auto": False,
    "etapes_max": 20,
    "afficher_reflexion": False,
}
if emplacements.config_agent().exists():
    CONFIG.update(json.loads(emplacements.config_agent().read_text(encoding="utf-8")))


def utiliser_tour(config=None):
    """Vrai si un deuxième PC (la tour) fait tourner l'IA. Réglage « utiliser_tour » ; s'il est absent
    (anciennes configs), déduit de la liste des serveurs (un serveur autre que « ce PC »)."""
    c = CONFIG if config is None else config
    if "utiliser_tour" in c:
        return bool(c["utiliser_tour"])
    return any(s.get("url") != "local" for s in c.get("serveurs") or [])

LMS = Path(os.path.expanduser(CONFIG.get("lms_local") or "~/.lmstudio/bin/lms.exe"))
ALLOWED = [WORKSPACE] + [Path(os.path.expanduser(p)).resolve() for p in CONFIG["dossiers_autorises"]]
AUTO = False          # passe à True en mode --task / --tache
BASE_URL = None  # choisi par ensure_server()


# --- Journal -----------------------------------------------------------------
def log(msg: str):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    with open(LOGS / f"{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def say(msg: str):
    print(msg)
    log(msg)


# --- Sécurité ----------------------------------------------------------------
def _safe_path(p: str) -> Path:
    """Chemin relatif -> workspace. Chemin absolu -> doit être dans un dossier autorisé."""
    path = Path(os.path.expanduser(p))
    path = (path if path.is_absolute() else WORKSPACE / path).resolve()
    if not any(path == a or a in path.parents for a in ALLOWED):
        raise PermissionError(
            f"Accès refusé : {path}. Dossiers autorisés : {', '.join(map(str, ALLOWED))}")
    return path


def _confirm(msg: str) -> bool:
    if AUTO:
        return True
    return input(f"\n⚠️  {msg}\n   Autoriser ? [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


def _to_trash(path: Path) -> Path:
    """Déplace un fichier/dossier dans corbeille/ au lieu de le supprimer."""
    dest = CORBEILLE / f"{datetime.now():%Y%m%d-%H%M%S}_{path.name}"
    shutil.move(str(path), str(dest))
    return dest


# --- Outils ------------------------------------------------------------------
def list_dir(path: str = ".") -> str:
    p = _safe_path(path)
    rows = []
    for c in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        st = c.stat()
        date = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
        if c.is_dir():
            rows.append(f"[D] {c.name}/  (modifié {date})")
        else:
            rows.append(f"[F] {c.name}  {st.st_size/1024:.0f} Ko  (modifié {date})")
    if len(rows) > 300:
        rows = rows[:300] + [f"... et {len(rows) - 300} autres"]
    return f"{p}\n" + ("\n".join(rows) or "(dossier vide)")


def read_file(path: str) -> str:
    text = _safe_path(path).read_text(encoding="utf-8", errors="replace")
    return text[:20000] + ("\n...[tronqué]" if len(text) > 20000 else "")


def write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    if not _confirm(f"Écrire {len(content)} caractères dans {p}"):
        return "Refusé par l'utilisateur."
    note = ""
    if p.exists():
        note = f" (ancienne version sauvegardée dans {_to_trash(p).name})"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Fichier écrit : {p}{note}"


def move_file(source: str, destination: str) -> str:
    src, dst = _safe_path(source), _safe_path(destination)
    if not src.exists():
        return f"Introuvable : {src}"
    if dst.is_dir():
        dst = dst / src.name
    if dst.exists():
        return f"La destination existe déjà : {dst}"
    if not _confirm(f"Déplacer {src} -> {dst}"):
        return "Refusé par l'utilisateur."
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Déplacé : {src} -> {dst}"


def create_folder(path: str) -> str:
    p = _safe_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Dossier prêt : {p}"


def delete_file(path: str) -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"Introuvable : {p}"
    if p in ALLOWED:
        return "Interdit : impossible de supprimer un dossier racine autorisé."
    if not _confirm(f"Mettre à la corbeille : {p}"):
        return "Refusé par l'utilisateur."
    return f"Mis à la corbeille (récupérable) : {_to_trash(p)}"


def disk_space() -> str:
    out = []
    for letter in "CDEFG":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            t, u, f = shutil.disk_usage(drive)
            out.append(f"{drive} libre {f/1e9:.1f} Go / {t/1e9:.1f} Go")
    return "\n".join(out)


def run_powershell(command: str) -> str:
    if AUTO and not CONFIG["powershell_en_auto"]:
        return "Interdit en mode automatique (powershell_en_auto = false dans config.json). Utilise les autres outils."
    if not _confirm(f"Exécuter :\n   {command}"):
        return "Refusé par l'utilisateur."
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else "")).strip()
    return f"(code {r.returncode})\n{out[:10000] or '(aucune sortie)'}"


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "local-agent/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read(200_000).decode("utf-8", errors="replace")
    raw = re.sub(r"<(script|style)[\s\S]*?</\1>", "", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw)[:8000]


S = {"type": "string"}
TOOLS = {
    "list_dir": (list_dir, "Liste un dossier avec taille et date de modification de chaque élément.",
                 {"path": {**S, "description": "Relatif au workspace, ou absolu dans un dossier autorisé"}}, []),
    "read_file": (read_file, "Lit un fichier texte.", {"path": S}, ["path"]),
    "write_file": (write_file, "Crée ou remplace un fichier texte (l'ancienne version va à la corbeille).",
                   {"path": S, "content": S}, ["path", "content"]),
    "move_file": (move_file, "Déplace ou renomme un fichier/dossier. Si la destination est un dossier existant, le fichier va dedans.",
                  {"source": S, "destination": S}, ["source", "destination"]),
    "create_folder": (create_folder, "Crée un dossier.", {"path": S}, ["path"]),
    "delete_file": (delete_file, "Met un fichier/dossier à la corbeille (récupérable).", {"path": S}, ["path"]),
    "disk_space": (disk_space, "Espace disque libre sur chaque lecteur.", {}, []),
    "run_powershell": (run_powershell, "Exécute une commande PowerShell (souvent interdit en mode automatique).",
                       {"command": S}, ["command"]),
    "fetch_url": (fetch_url, "Télécharge une page web et renvoie son texte.", {"url": S}, ["url"]),
}
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": n, "description": d,
        "parameters": {"type": "object", "properties": p, "required": r}}}
    for n, (_, d, p, r) in TOOLS.items()
]


def system_prompt() -> str:
    mode = ("MODE AUTOMATIQUE : personne ne surveille. Agis avec prudence, n'invente rien, "
            "et termine par un court compte rendu de ce que tu as fait."
            if AUTO else "Mode interactif : l'utilisateur valide chaque action.")
    return f"""Tu es un assistant IA local sur le PC Windows 11 de l'utilisateur.
Dossier de travail (chemins relatifs) : {WORKSPACE}
Dossiers auxquels tu as accès : {', '.join(map(str, ALLOWED))}
Dossier personnel : {Path.home()}
{mode}
Règles :
- Utilise les outils plutôt que de supposer. Regarde un dossier (list_dir) avant d'agir dessus.
- Ne supprime que ce qui est clairement demandé ; la suppression envoie à la corbeille.
- Réponds en français, de façon concise.
Date actuelle : {datetime.now():%Y-%m-%d %H:%M}"""


# --- LM Studio (local) -------------------------------------------------------------
# Tout tourne sur CE PC. Au démarrage : choix du moteur selon la carte graphique
# (NVIDIA -> CUDA le plus récent, AMD / Intel -> Vulkan, sinon CPU), chargement du modèle
# avec toutes les couches sur la carte graphique ; à la fin : déchargement (VRAM libérée).
SERVEUR = "ce PC"
A_DECHARGER = []  # modèles chargés par le script, déchargés à la fin
LMSTUDIO_OUVERT_PAR_SCRIPT = False  # True si LM Studio était fermé -> refermé à la fin


def _lmstudio_ouvert():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Bionic.exe", "/NH"],
                       capture_output=True, text=True, errors="replace")
    return "bionic.exe" in r.stdout.lower()


def _reachable(url):
    try:
        urllib.request.urlopen(f"{url}/models", timeout=3)
        return True
    except Exception:
        return False


def _lms(*args, timeout=600):
    exe = str(LMS) if LMS.exists() else "lms"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def cartes_graphiques():
    """Noms des cartes graphiques de ce PC (Windows)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_VideoController).Name"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def type_gpu():
    """'nvidia', 'amd', 'intel' ou 'cpu' — la carte dédiée passe avant la carte intégrée."""
    noms = " | ".join(cartes_graphiques()).lower()
    if "nvidia" in noms:
        return "nvidia"
    if "radeon" in noms or "amd" in noms:
        return "amd"
    if "intel" in noms and ("arc" in noms or "iris" in noms or "uhd" in noms):
        return "intel"
    return "cpu"


def _version(nom):
    """'llama.cpp-...@2.72.0' -> (2, 72, 0)"""
    v = nom.split("@")[-1] if "@" in nom else "0"
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _cuda(nom):
    """Version CUDA dans le nom du moteur : cuda13 -> 13, cuda12 -> 12, cuda -> 11 (ancien)."""
    m = re.search(r"nvidia-cuda(\d*)", nom)
    return int(m.group(1)[:2]) if m and m.group(1) else (11 if m else 0)


def _moteurs_installes():
    """Moteurs llama.cpp installés -> {nom@version: sélectionné?}"""
    res = {}
    for ligne in _lms("runtime", "ls").stdout.splitlines():
        m = re.match(r"\s*(llama\.cpp-\S+@\S+)", ligne)
        if m:
            res[m.group(1)] = "✓" in ligne
    return res


def choisir_moteur():
    """Sélectionne dans LM Studio le meilleur moteur pour la carte graphique de ce PC."""
    voulu = CONFIG.get("gpu", "auto")
    gpu = type_gpu() if voulu == "auto" else voulu
    famille = {"nvidia": "cuda", "cuda": "cuda", "amd": "vulkan", "intel": "vulkan",
               "vulkan": "vulkan"}.get(gpu, "cpu")
    if famille == "cuda":
        # le CUDA le plus récent compatible avec ce PC (LM Studio vérifie le pilote)
        dispo = _lms("runtime", "get", "--list", "llama.cpp").stdout
        variantes = sorted(set(re.findall(r"llama\.cpp-win-x86_64-nvidia-cuda\d*-avx2", dispo)), key=_cuda)
        if variantes:
            cible = variantes[-1]
            if not any(n.startswith(cible + "@") for n in _moteurs_installes()):
                say(f"   Téléchargement du moteur {cible} (CUDA {_cuda(cible)})...")
                _lms("runtime", "get", cible, "-y", timeout=1800)
    installes = _moteurs_installes()
    if famille == "cuda":
        candidats = [n for n in installes if "nvidia-cuda" in n]
        cle = lambda n: (_cuda(n), _version(n))  # noqa: E731
    elif famille == "vulkan":
        candidats = [n for n in installes if "vulkan" in n]
        cle = _version
    else:
        candidats = [n for n in installes if re.match(r"llama\.cpp-win-x86_64-avx2@", n)]
        cle = _version
    if not candidats:
        say(f"   ⚠️ Aucun moteur {famille} installé dans LM Studio : on garde le moteur actuel "
            "(installe-le dans LM Studio → Runtime)")
        return
    meilleur = max(candidats, key=cle)
    if installes.get(meilleur):
        say(f"🎮 Carte graphique : {gpu} → moteur {meilleur} (déjà sélectionné)")
        return
    say(f"🎮 Carte graphique : {gpu} → sélection du moteur {meilleur}")
    _lms("runtime", "select", meilleur)
    if CONFIG["modele"] in _lms("ps").stdout:  # recharger avec le nouveau moteur
        _lms("unload", CONFIG["modele"])


def ensure_server():
    """Démarre le serveur LM Studio de ce PC, choisit le moteur et charge le modèle."""
    global BASE_URL
    global LMSTUDIO_OUVERT_PAR_SCRIPT
    candidates = [f"http://localhost:{p}/v1" for p in (1234, 1235)]
    url = next((u for u in candidates if _reachable(u)), None)
    if not url and not _lmstudio_ouvert() and CONFIG.get("fermer_lmstudio_apres", True):
        LMSTUDIO_OUVERT_PAR_SCRIPT = True  # « lms server start » va l'ouvrir : on le refermera à la fin
    if not url:
        say("Démarrage du serveur LM Studio...")
        _lms("server", "start")
        time.sleep(3)
        url = next((u for u in candidates if _reachable(u)), None)
        if not url:
            say("❌ Serveur LM Studio injoignable. Ouvre LM Studio ou lance : lms server start")
            sys.exit(1)
    BASE_URL = url
    choisir_moteur()
    if CONFIG["modele"] not in _lms("ps").stdout:
        say(f"   Chargement de {CONFIG['modele']} (toutes les couches sur la carte graphique)...")
        t = time.time()
        _lms("load", CONFIG["modele"], "--context-length", str(CONFIG["contexte"]), "--gpu", "max", "-y")
        say(f"   Modèle chargé en {time.time() - t:.0f} s")
        if CONFIG.get("decharger_a_la_fin", True):
            A_DECHARGER.append(CONFIG["modele"])
    say(f"🧠 Modèle prêt ({BASE_URL})")


def _reprendre_boucle():
    """Reprend ce que les passages précédents d'une boucle ont laissé ouvert (à refermer par le dernier)."""
    global LMSTUDIO_OUVERT_PAR_SCRIPT
    import boucle
    etat = boucle.reprendre()
    for m in etat.get("a_decharger", []):
        if m not in A_DECHARGER:
            A_DECHARGER.append(m)
    LMSTUDIO_OUVERT_PAR_SCRIPT = LMSTUDIO_OUVERT_PAR_SCRIPT or bool(etat.get("lmstudio_local"))


def _garder_pour_le_passage_suivant():
    """Passage d'une boucle qui n'est pas le dernier : rien n'est fermé, le suivant reprend le tout."""
    import boucle
    if not boucle.garder_ouvert():
        return False
    boucle.transmettre({"a_decharger": list(A_DECHARGER), "lmstudio_local": LMSTUDIO_OUVERT_PAR_SCRIPT})
    A_DECHARGER.clear()
    say("⏭️ Modèle et LM Studio gardés ouverts pour le passage suivant")
    return True


def liberer_modele():
    """Décharge le modèle s'il a été chargé par le script (appelé automatiquement à la fin).
    Dans une boucle de passages, seul le dernier passage referme (voir boucle.py)."""
    _reprendre_boucle()
    if _garder_pour_le_passage_suivant():
        return
    while A_DECHARGER:
        m = A_DECHARGER.pop()
        try:
            _lms("unload", m, timeout=120)
            log("🧹 Modèle déchargé (mémoire de la carte graphique libérée)")
            print("🧹 Modèle déchargé")
        except Exception as e:
            log(f"⚠️ Déchargement impossible : {e}")
    global LMSTUDIO_OUVERT_PAR_SCRIPT
    if LMSTUDIO_OUVERT_PAR_SCRIPT:
        LMSTUDIO_OUVERT_PAR_SCRIPT = False
        _lms("server", "stop", timeout=60)
        subprocess.run(["taskkill", "/IM", "Bionic.exe", "/F"], capture_output=True)
        log("🧹 LM Studio fermé (il avait été ouvert par le script)")
        print("🧹 LM Studio fermé")


import atexit  # noqa: E402
atexit.register(liberer_modele)


def post_chat(req_body):
    body = json.dumps(req_body).encode()
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read())["choices"][0]["message"]



def chat(messages):
    req = {"model": CONFIG["modele"], "messages": messages, "tools": TOOL_SCHEMAS, "temperature": 0.6}
    if not CONFIG.get("reflexion", False):
        req["reasoning_effort"] = "none"  # sans réflexion : environ 10x plus rapide
    return post_chat(req)


def run_turn(messages):
    for _ in range(CONFIG["etapes_max"]):
        msg = chat(messages)
        thinking = msg.get("reasoning_content") or msg.get("reasoning")
        if thinking and CONFIG["afficher_reflexion"]:
            print(f"\033[90m💭 {thinking.strip()}\033[0m")

        entry = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            entry["tool_calls"] = msg["tool_calls"]
        messages.append(entry)
        if not msg.get("tool_calls"):
            return msg.get("content") or ""

        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                say(f"🔧 {name}({', '.join(f'{k}={str(v)[:80]!r}' for k, v in args.items())})")
                result = str(TOOLS[name][0](**args))
            except Exception as e:
                result = f"Erreur : {e}"
            log(f"   -> {result[:300]}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return "(limite d'étapes atteinte)"


# --- Points d'entrée -----------------------------------------------------------
def run_auto(consigne: str, nom: str):
    global AUTO
    AUTO = True
    log(f"===== TÂCHE AUTO « {nom} » =====")
    log(f"Consigne : {consigne}")
    ensure_server()
    messages = [{"role": "system", "content": system_prompt()},
                {"role": "user", "content": consigne}]
    t = time.time()
    try:
        say(f"Compte rendu : {run_turn(messages)}")
    except Exception as e:
        say(f"❌ Échec : {e}")
        sys.exit(1)
    log(f"===== Fin ({time.time() - t:.0f} s) =====\n")


def run_chat():
    ensure_server()
    print(f"🤖 Agent prêt ({CONFIG['modele']})")
    print(f"   Accès : {', '.join(map(str, ALLOWED))}")
    print("   /reset pour effacer la mémoire, /quit pour quitter\n")
    messages = [{"role": "system", "content": system_prompt()}]
    while True:
        try:
            user = input("\033[1mToi > \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user == "/quit":
            break
        if user == "/reset":
            messages = messages[:1]
            print("Mémoire effacée.\n")
            continue
        log(f"Toi > {user}")
        messages.append({"role": "user", "content": user})
        try:
            reply = run_turn(messages)
            log(f"Agent > {reply}")
            print(f"\n\033[32mAgent >\033[0m {reply}\n")
        except urllib.error.URLError as e:
            print(f"❌ Erreur de connexion : {e}\n")


def main():
    ap = argparse.ArgumentParser(description="Agent IA local (LM Studio)")
    ap.add_argument("--task", help="consigne à exécuter automatiquement")
    ap.add_argument("--tache", help="nom d'un fichier taches/<nom>.txt à exécuter automatiquement")
    a = ap.parse_args()
    if a.tache:
        f = TACHES / f"{a.tache}.txt"
        if not f.exists():
            log(f"❌ Tâche introuvable : {f}")
            sys.exit(f"Tâche introuvable : {f}")
        run_auto(f.read_text(encoding="utf-8").strip(), a.tache)
    elif a.task:
        run_auto(a.task, "ligne de commande")
    else:
        run_chat()


if __name__ == "__main__":
    main()
