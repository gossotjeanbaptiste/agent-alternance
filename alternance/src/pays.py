"""Le site d'une entreprise est-il bien celui d'une entreprise en France ?

- extension française (.fr, outre-mer, .bzh, .paris…) : oui ;
- extension d'un autre pays (.lu, .be, .ch, .de, .us, .uk, .ca…) : non ;
- extension neutre (.com, .net, .eu, .io…) : oui seulement avec une preuve française dans les pages lues :
  code postal ou ville de l'entreprise, téléphone français (+33 ou 10 chiffres), SIRET / SIREN / RCS.
  Un site simplement écrit en français ne suffit pas (Belgique, Suisse, Luxembourg, Québec…).
"""
import re
import unicodedata
import urllib.parse

TLD_FRANCE = {"fr", "re", "gp", "mq", "gf", "yt", "pm", "nc", "pf", "wf", "tf", "bl", "mf",
              "bzh", "paris", "alsace", "corsica", "bretagne"}
# extensions à deux lettres utilisées partout comme des extensions neutres (pas un pays en pratique)
DEUX_LETTRES_NEUTRES = {"eu", "io", "co", "ai", "me", "tv", "fm", "ly", "cc", "gg", "to", "app"}
PAYS = {"lu": "Luxembourg", "be": "Belgique", "ch": "Suisse", "de": "Allemagne", "us": "États-Unis",
        "uk": "Royaume-Uni", "ca": "Canada", "it": "Italie", "es": "Espagne", "nl": "Pays-Bas", "pt": "Portugal",
        "ma": "Maroc", "tn": "Tunisie", "dz": "Algérie", "sn": "Sénégal", "ci": "Côte d'Ivoire", "mc": "Monaco",
        "at": "Autriche", "ie": "Irlande", "pl": "Pologne", "in": "Inde", "cn": "Chine", "jp": "Japon"}

# preuves d'une adresse ou d'une entreprise française
TEL_FRANCE = re.compile(r"(?:\+33|0033)\s?\(?0?\)?\s?[1-9](?:[\s.-]?\d{2}){4}\b|\b0[1-9](?:[\s.-]?\d{2}){4}\b")
# (le RCS existe aussi au Luxembourg : « R.C.S. Luxembourg B123456 » ne compte pas)
REGISTRE = re.compile(r"\b(?:siret|siren|n°\s?tva\s?intracom\w*\s?:?\s?fr\d|"
                      r"r\.?\s?c\.?\s?s\b(?![.\s]*(?:de\s+)?luxembourg))", re.I)
# indices d'un autre pays (affichés dans la raison quand il n'y a aucune preuve française)
ETRANGER = [(re.compile(r"\+352|\bL-\d{4}\b|\bluxembourg\b", re.I), "Luxembourg"),
            (re.compile(r"\+32\b|\bB-\d{4}\b|\bbelgique\b|\bbelgium\b", re.I), "Belgique"),
            (re.compile(r"\+41\b|\bCH-\d{4}\b|\bsuisse\b|\bswitzerland\b", re.I), "Suisse"),
            (re.compile(r"\+1[\s(-]|\bunited states\b|\busa\b|\bU\.S\.A\.?", re.I), "États-Unis"),
            (re.compile(r"\+44\b|\bunited kingdom\b", re.I), "Royaume-Uni")]


def _ascii(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def extension(url):
    """« https://www.xefi.fr/contact » -> « fr »."""
    hote = urllib.parse.urlparse(url if "//" in url else "https://" + url).hostname or ""
    return hote.rsplit(".", 1)[-1].lower() if "." in hote else ""


def pays_de_l_extension(url):
    """« France », le nom d'un autre pays, ou "" (extension neutre : il faut regarder le contenu)."""
    ext = extension(url)
    if ext in TLD_FRANCE:
        return "France"
    if len(ext) == 2 and ext not in DEUX_LETTRES_NEUTRES:
        return PAYS.get(ext, f"pays « .{ext} »")
    return ""


def preuves_francaises(texte, lieu=""):
    """Preuves trouvées dans le texte des pages : ["code postal 69003", "téléphone français", …]."""
    from tableau import ville
    preuves = []
    cp = re.search(r"\b(\d{5})\b", lieu or "")
    if cp and re.search(rf"\b{cp.group(1)}\b", texte):
        preuves.append(f"code postal {cp.group(1)}")
    v = _ascii(ville(lieu))
    if len(v) >= 4 and v in _ascii(texte):
        preuves.append(f"ville {ville(lieu)}")
    if TEL_FRANCE.search(texte):
        preuves.append("téléphone français")
    if REGISTRE.search(texte):
        preuves.append("SIRET / RCS")
    return preuves


def indices_etrangers(texte):
    return [p for motif, p in ETRANGER if motif.search(texte)]


def verdict(url, textes, lieu=""):
    """(en France ?, raison) pour le site url d'après le texte de ses pages (liste de chaînes)."""
    pays = pays_de_l_extension(url)
    if pays == "France":
        return True, f"extension .{extension(url)}"
    if pays:
        return False, f"site d'un autre pays ({pays}, .{extension(url)})"
    texte = " ".join(re.sub(r"<[^>]+>", " ", t or "") for t in textes)
    preuves = preuves_francaises(texte, lieu)
    if preuves:
        return True, ", ".join(preuves)
    etrangers = indices_etrangers(texte)
    return False, ("aucune preuve d'une adresse en France" +
                   (f" (indices : {', '.join(etrangers)})" if etrangers else ""))
