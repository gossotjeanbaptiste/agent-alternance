"""Affichage du rapport rédigé par le modèle : Markdown simple (titres, listes, gras, italique) -> HTML sûr.
Le texte est échappé d'abord : rien de ce qu'écrit le modèle ne peut devenir du code dans la page."""
import re
from html import escape

from markupsafe import Markup


def _en_ligne(t):
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)


def en_html(md):
    html, liste = [], False
    for ligne in (md or "").splitlines():
        brut = ligne.strip()
        t = _en_ligne(escape(brut, quote=False))
        puce = re.match(r"^([-*•]|\d+[.)])\s+(.*)", t)
        if liste and not puce:
            html.append("</ul>")
            liste = False
        if not brut or re.fullmatch(r"[-*_]{3,}", brut):
            continue
        if (titre := re.match(r"^(#{1,4})\s*(.*)", t)):
            niveau = min(len(titre.group(1)) + 1, 4)       # « # » -> h2 (le h1 est celui de la page)
            html.append(f"<h{niveau}>{titre.group(2)}</h{niveau}>")
        elif puce:
            if not liste:
                html.append("<ul>")
                liste = True
            html.append(f"<li>{puce.group(2)}</li>")
        else:
            html.append(f"<p>{t}</p>")
    if liste:
        html.append("</ul>")
    return Markup("\n".join(html))
