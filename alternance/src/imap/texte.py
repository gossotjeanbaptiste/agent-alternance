"""Lecture d'un mail IMAP : dates, adresses, en-têtes encodés, texte et HTML du corps."""
import email.header
import html
import re
from email.utils import getaddresses, parsedate_to_datetime

MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _date_imap(d):
    return f"{d.day:02d}-{MOIS[d.month - 1]}-{d.year}"


def _date_locale(valeur):
    """En-tête Date -> datetime locale sans fuseau (comme pour Outlook)."""
    try:
        d = parsedate_to_datetime(valeur)
        if d.tzinfo:
            d = d.astimezone().replace(tzinfo=None)
        return d.replace(second=0, microsecond=0)
    except Exception:
        return None


def _adresses(*valeurs):
    return [a.lower() for _, a in getaddresses([v for v in valeurs if v]) if "@" in a]


def _decoder(valeur):
    try:
        return str(email.header.make_header(email.header.decode_header(valeur or "")))
    except Exception:
        return valeur or ""


def _texte(msg):
    """Texte d'un mail : la partie texte si elle existe, sinon le HTML sans balises."""
    texte, page = "", ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_disposition() == "attachment":
            continue
        try:
            contenu = part.get_payload(decode=True)
            if contenu is None:
                continue
            contenu = contenu.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if part.get_content_type() == "text/plain" and not texte:
            texte = contenu
        elif part.get_content_type() == "text/html" and not page:
            page = contenu
    if texte:
        return texte
    page = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", page)
    return html.unescape(re.sub(r"<[^>]+>", "", page))


def _texte_en_html(msg):
    """Corps HTML du mail d'origine s'il existe (rendu fidèle), sinon son texte."""
    try:
        partie = msg.get_body(preferencelist=("html", "plain"))
        contenu = partie.get_content()
        if partie.get_content_type() == "text/html":
            return re.sub(r"(?is)^.*?<body[^>]*>|</body>.*$", "", contenu)
        return html.escape(contenu).replace("\n", "<br>")
    except Exception:
        return ""
