"""Trouver le site officiel d'une entreprise : domaine deviné d'après son nom, sinon recherche web (DuckDuckGo)."""
import html as html_lib
import re
import urllib.parse
import urllib.request

import pays
import reglages
import sites
from .noms import JURIDIQUE, _mots, _mots_nom, _norm, _repere_lieu, ressemble
from .pages import UA, _racine

RECHERCHE = {"bloquee": False, "derniere": 0.0}


def _bases(nom):
    """Débuts de domaine à essayer : « Lambert Morel » -> lambertmorel, lambert-morel ; [] si nom trop générique."""
    tous = [m for m in _norm(nom).split() if m not in JURIDIQUE]  # « N Tech Services » -> n, tech, services
    utiles = _mots(nom)
    if not utiles:  # que des mots génériques : impossible de deviner sans se tromper
        return []
    sigle = [m for m in _mots_nom(nom) if m not in JURIDIQUE]
    if sigle != tous:
        tous = sigle
    bases = []
    for mots in (tous, utiles):
        if mots:
            bases += ["".join(mots), "-".join(mots)]
    if len(tous) >= 2 and len(tous[0]) <= 2:  # « N Tech » -> ntech
        bases.append(tous[0] + tous[1])
    return [b for b in dict.fromkeys(bases) if len(b.replace("-", "")) >= 5]


def _page_cite_l_entreprise(page, nom, lieu):
    """La page cite le nom (et la ville ou le code postal si le nom est court, donc ambigu)."""
    utiles = _mots(nom)
    texte = _norm(re.sub(r"<[^>]+>", " ", page)).replace(" ", "")
    if not all(m in texte for m in utiles):
        return False
    if len("".join(utiles)) < 6:  # nom court : on vérifie aussi la ville ou le code postal
        cp, ville = _repere_lieu(lieu)
        return bool((cp and cp in texte) or (len(ville) >= 3 and ville in texte))
    return True


def deviner_site(nom, lieu=""):
    """Essaie nom.fr / nom.com / nom-en-tirets.fr… ; garde le premier qui répond sans rediriger
    ailleurs et dont la page cite bien l'entreprise (et sa ville si le nom est court, donc ambigu)."""
    for base in _bases(nom):
        for ext in ("fr", "com", "eu", "net"):
            url = f"https://{base}.{ext}"
            try:
                page, final = sites._lire(url, 300_000)
            except Exception:
                continue
            if _racine(final) != f"{base}.{ext}":  # redirigé vers un autre site : pas le bon
                continue
            if not _page_cite_l_entreprise(page, nom, lieu):
                continue
            if not sites.site_en_france(final, lieu, [page])[0]:   # même nom, mais entreprise d'un autre pays
                continue
            u = urllib.parse.urlparse(final)
            return f"{u.scheme}://{u.netloc}"
    return ""


def _resultats_web(nom, lieu):
    """Liens des résultats DuckDuckGo pour « nom ville » ; None si la recherche est bloquée ou impossible."""
    attente = float(reglages.valeur("sites.attente_recherche_s")) - (sites.time.time() - RECHERCHE["derniere"])
    if attente > 0:  # recherches espacées, pour rester poli
        sites.time.sleep(attente)
    RECHERCHE["derniere"] = sites.time.time()
    ville = re.sub(r"\d{5}", "", (lieu or "").split(",")[-1]).strip()
    q = urllib.parse.urlencode({"q": f"{nom} {ville}".strip()}).encode()
    try:
        req = urllib.request.Request("https://html.duckduckgo.com/html/", data=q, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            page = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    if "result__a" not in page:  # page anti-robot : on arrête les recherches pour ce passage
        RECHERCHE["bloquee"] = True
        return None
    liens = []
    for lien in re.findall(r'class="result__a" href="([^"]+)"', page)[:8]:
        lien = html_lib.unescape(lien)
        m = re.search(r"uddg=([^&]+)", lien)
        liens.append(urllib.parse.unquote(m.group(1)) if m else lien)
    return liens


def _racine_en_france(racine, lieu):
    """Site trouvé par la recherche : gardé s'il est en France (extension, sinon preuve dans le site)."""
    if not sites.verifier_france() or pays.pays_de_l_extension(racine) == "France":
        return True
    if pays.pays_de_l_extension(racine):    # .lu, .be, .us… : écarté sans le lire
        return False
    try:                                     # .com, .net… : preuve française cherchée dans le site
        page, final = sites._lire(racine, 300_000)
    except Exception:
        return False
    return sites.site_en_france(final, lieu, [page])[0]


def trouver_site(nom, lieu=""):
    """Site officiel de l'entreprise (domaine deviné, sinon recherche web), ou ""."""
    site = sites.deviner_site(nom, lieu)
    if site or RECHERCHE["bloquee"]:
        return site
    for lien in _resultats_web(nom, lieu) or []:
        if not (lien.startswith("http") and ressemble(nom, lien)):
            continue
        u = urllib.parse.urlparse(lien)
        racine = f"{u.scheme}://{u.netloc}"
        if _racine_en_france(racine, lieu):
            return racine
    return ""
