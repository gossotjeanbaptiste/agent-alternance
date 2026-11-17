"""Outils PowerShell et web, liste des outils donnée au modèle, consigne système."""
import re
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

import agent
from .fichiers import create_folder, delete_file, disk_space, list_dir, move_file, read_file, write_file


def run_powershell(command: str) -> str:
    if agent.AUTO and not agent.CONFIG["powershell_en_auto"]:
        return "Interdit en mode automatique (powershell_en_auto = false dans config.json). Utilise les autres outils."
    if not agent._confirm(f"Exécuter :\n   {command}"):
        return "Refusé par l'utilisateur."
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=agent.WORKSPACE, capture_output=True, text=True, timeout=300,
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
            if agent.AUTO else "Mode interactif : l'utilisateur valide chaque action.")
    return f"""Tu es un assistant IA local sur le PC Windows 11 de l'utilisateur.
Dossier de travail (chemins relatifs) : {agent.WORKSPACE}
Dossiers auxquels tu as accès : {', '.join(map(str, agent.ALLOWED))}
Dossier personnel : {Path.home()}
{mode}
Règles :
- Utilise les outils plutôt que de supposer. Regarde un dossier (list_dir) avant d'agir dessus.
- Ne supprime que ce qui est clairement demandé ; la suppression envoie à la corbeille.
- Réponds en français, de façon concise.
Date actuelle : {datetime.now():%Y-%m-%d %H:%M}"""
