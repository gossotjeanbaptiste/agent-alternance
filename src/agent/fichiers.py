"""Outils de fichiers proposés au modèle : seulement dans le workspace et les dossiers autorisés,
rien n'est vraiment supprimé (tout passe par la corbeille), confirmation demandée hors mode automatique."""
import os
import shutil
from datetime import datetime
from pathlib import Path

import agent


# --- Sécurité ----------------------------------------------------------------
def _safe_path(p: str) -> Path:
    """Chemin relatif -> workspace. Chemin absolu -> doit être dans un dossier autorisé."""
    path = Path(os.path.expanduser(p))
    path = (path if path.is_absolute() else agent.WORKSPACE / path).resolve()
    if not any(path == a or a in path.parents for a in agent.ALLOWED):
        raise PermissionError(
            f"Accès refusé : {path}. Dossiers autorisés : {', '.join(map(str, agent.ALLOWED))}")
    return path


def _confirm(msg: str) -> bool:
    if agent.AUTO:
        return True
    return input(f"\n⚠️  {msg}\n   Autoriser ? [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


def _to_trash(path: Path) -> Path:
    """Déplace un fichier/dossier dans corbeille/ au lieu de le supprimer."""
    dest = agent.CORBEILLE / f"{datetime.now():%Y%m%d-%H%M%S}_{path.name}"
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
    if p in agent.ALLOWED:
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
