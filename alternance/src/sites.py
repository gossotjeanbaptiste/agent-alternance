"""Sites web des entreprises : trouver le site, puis une adresse mail ou un formulaire de contact.

1. Pas de site connu : on essaie les domaines évidents (nom.fr, nom.com, nom-en-tirets.fr…) en
   vérifiant que la page cite bien l'entreprise ; sinon recherche web (DuckDuckGo, version HTML),
   en gardant le premier résultat dont le domaine ressemble au nom (les annuaires sont écartés).
   Si DuckDuckGo répond par sa page anti-robot, on n'insiste pas jusqu'à la fin du passage.
2. Sur le site : page d'accueil, puis les pages « contact / recrutement / carrière » trouvées
   dans ses liens (et quelques adresses classiques). On y cherche :
   - une adresse affichée (y compris masquée : « [at] », protection Cloudflare) ;
   - un formulaire de contact (champ de message).
"""
import html as html_lib
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from mails import domaine

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept-Language": "fr-FR,fr;q=0.9"}

# sites qui parlent de l'entreprise sans être le sien
ANNUAIRES = ("societe.com", "pappers", "pagesjaunes", "kompass", "dnb.com", "linkedin", "facebook",
             "instagram", "twitter", "x.com", "youtube", "wikipedia", "mappy", "infogreffe", "verif.com",
             "manageo", "annuaire", "indeed", "welcometothejungle", "glassdoor", "labonnealternance",
             "france-travail", "pole-emploi", "hellowork", "findglocal", "corporama", "lefigaro", "google",
             "bing.com", "apple.com", "yelp", "tripadvisor", "infonet", "entreprises.lefigaro", "societeinfo",
             "score3", "ellisphere", "bfmtv", "francebleu",
             "elioplus", "superordi", "118000", "118712", "justacote", "cylex", "hoodspot", "doctrine")

# messageries grand public : acceptées si l'adresse est affichée sur le site même de l'entreprise
GRAND_PUBLIC = ("gmail.com", "orange.fr", "wanadoo.fr", "free.fr", "outlook.fr", "outlook.com", "hotmail.fr",
                "hotmail.com", "laposte.net", "sfr.fr", "yahoo.fr", "live.fr", "icloud.com")

MOTS_CONTACT = ("contact", "nous-contacter", "contactez", "recrutement", "carriere", "carrieres", "emploi",
                "jobs", "join", "rejoindre", "candidature", "postuler", "mentions-legales", "a-propos", "about")
PAGES_CLASSIQUES = ("/contact", "/nous-contacter", "/contact/", "/contact.html", "/recrutement", "/mentions-legales")
FORMES = {"sarl", "sas", "sasu", "eurl", "sa", "sci", "snc", "groupe", "group", "france", "societe", "soc",
          "ste", "et", "de", "des", "du", "la", "le", "les", "services", "service", "informatique"}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _mots_nom(nom):
    """Mots du nom, initiales regroupées : « E.S.I. France » -> esi, france."""
    mots, sigle = [], ""
    for m in _norm(nom).split():
        if len(m) == 1:
            sigle += m
            continue
        if sigle:
            mots.append(sigle)
            sigle = ""
        mots.append(m)
    return mots + ([sigle] if sigle else [])


def _lire(url, maxi=500_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        if "html" not in (r.headers.get("Content-Type") or "html"):
            return "", r.geturl()
        return r.read(maxi).decode("utf-8", errors="replace"), r.geturl()


def _racine(url):
    u = urllib.parse.urlparse(url if url.startswith("http") else "https://" + url)
    return re.sub(r"^www\.", "", u.netloc.lower())


def ressemble(nom, url):
    """Vrai si le nom de domaine correspond au nom de l'entreprise (berger-levrault.com ↔ Berger Levrault)."""
    dom = _racine(url)
    if not dom or any(a in dom for a in ANNUAIRES):
        return False
    base = re.sub(r"[^a-z0-9]", "", dom.rsplit(".", 1)[0])
    mots = _mots(nom)
    colle = "".join(mots)
    if len(colle) >= 4 and colle in base:
        return True
    return bool(mots) and all(m in base for m in mots)


def _mots(nom):
    """Mots qui distinguent l'entreprise (sans « SARL », « France », « Services »…)."""
    mots = [m for m in _mots_nom(nom) if m not in FORMES]
    return [m for m in mots if len(m) >= 3] or [m for m in mots if len(m) >= 2]


JURIDIQUE = {"sarl", "sas", "sasu", "eurl", "sa", "sci", "snc", "soc", "ste", "societe", "et", "de", "des",
             "du", "la", "le", "les"}


def _repere_lieu(lieu):
    """(code postal, ville) tirés d'une adresse « 12 rue X 69000 Lyon »."""
    cp = re.search(r"\b(\d{5})\b", lieu or "")
    ville = re.sub(r"\d{5}|cedex", " ", (lieu or "").split(",")[-1], flags=re.I)
    if cp:
        ville = (lieu or "")[cp.end():] or ville
    return (cp.group(1) if cp else ""), _norm(ville).replace(" ", "")


def deviner_site(nom, lieu=""):
    """Essaie nom.fr / nom.com / nom-en-tirets.fr… ; garde le premier qui répond sans rediriger
    ailleurs et dont la page cite bien l'entreprise (et sa ville si le nom est court, donc ambigu)."""
    tous = [m for m in _norm(nom).split() if m not in JURIDIQUE]  # « N Tech Services » -> n, tech, services
    utiles = _mots(nom)
    if not utiles:  # que des mots génériques : impossible de deviner sans se tromper
        return ""
    sigle = [m for m in _mots_nom(nom) if m not in JURIDIQUE]
    if sigle != tous:
        tous = sigle
    bases = []
    for mots in (tous, utiles):
        if mots:
            bases += ["".join(mots), "-".join(mots)]
    if len(tous) >= 2 and len(tous[0]) <= 2:  # « N Tech » -> ntech
        bases.append(tous[0] + tous[1])
    bases = [b for b in dict.fromkeys(bases) if len(b.replace("-", "")) >= 5]
    for base in bases:
        for ext in ("fr", "com", "eu", "net"):
            url = f"https://{base}.{ext}"
            try:
                page, final = _lire(url, 300_000)
            except Exception:
                continue
            if _racine(final) != f"{base}.{ext}":  # redirigé vers un autre site : pas le bon
                continue
            texte = _norm(re.sub(r"<[^>]+>", " ", page)).replace(" ", "")
            if not all(m in texte for m in utiles):
                continue
            if len("".join(utiles)) < 6:  # nom court : on vérifie aussi la ville ou le code postal
                cp, ville = _repere_lieu(lieu)
                if not ((cp and cp in texte) or (len(ville) >= 3 and ville in texte)):
                    continue
            u = urllib.parse.urlparse(final)
            return f"{u.scheme}://{u.netloc}"
    return ""


RECHERCHE = {"bloquee": False, "derniere": 0.0}


def trouver_site(nom, lieu=""):
    """Site officiel de l'entreprise (domaine deviné, sinon recherche web), ou ""."""
    site = deviner_site(nom, lieu)
    if site or RECHERCHE["bloquee"]:
        return site
    attente = 4 - (time.time() - RECHERCHE["derniere"])  # recherches espacées, pour rester poli
    if attente > 0:
        time.sleep(attente)
    RECHERCHE["derniere"] = time.time()
    ville = re.sub(r"\d{5}", "", (lieu or "").split(",")[-1]).strip()
    q = urllib.parse.urlencode({"q": f"{nom} {ville}".strip()}).encode()
    try:
        req = urllib.request.Request("https://html.duckduckgo.com/html/", data=q, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            page = r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    if "result__a" not in page:  # page anti-robot : on arrête les recherches pour ce passage
        RECHERCHE["bloquee"] = True
        return ""
    for lien in re.findall(r'class="result__a" href="([^"]+)"', page)[:8]:
        lien = html_lib.unescape(lien)
        m = re.search(r"uddg=([^&]+)", lien)
        lien = urllib.parse.unquote(m.group(1)) if m else lien
        if lien.startswith("http") and ressemble(nom, lien):
            u = urllib.parse.urlparse(lien)
            return f"{u.scheme}://{u.netloc}"
    return ""


def _cloudflare(code):
    k = int(code[:2], 16)
    return "".join(chr(int(code[i:i + 2], 16) ^ k) for i in range(2, len(code), 2))


def _adresses(html, dom):
    t = html_lib.unescape(html)
    t = re.sub(r"\s*[\[\(\{]\s*(at|arobase)\s*[\]\)\}]\s*", "@", t, flags=re.I)
    t = re.sub(r"\s*[\[\(\{]\s*(dot|point)\s*[\]\)\}]\s*", ".", t, flags=re.I)
    trouvees = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", t)
    for code in re.findall(r'data-cfemail="([0-9a-f]+)"', html):
        try:
            trouvees.append(_cloudflare(code))
        except Exception:
            pass
    res = []
    for m in trouvees:
        m = m.lower().strip(".")
        d = domaine(m)
        if (re.search(r"\.(png|jpe?g|gif|svg|webp|css|js)$", m) or "sentry" in d or "example" in d
                or not re.search(r"\.[a-z]{2,}$", d)):  # « search@0.0.206 » : pas une vraie adresse
            continue
        if d.endswith(dom) or dom.endswith(d) or d in GRAND_PUBLIC:
            res.append(m)
    return res


def _a_un_formulaire(html):
    """Formulaire de contact : un <form> avec un champ de message, ou une extension de formulaires connue."""
    for f in re.findall(r"<form[\s\S]*?</form>", html, flags=re.I):
        if re.search(r"<textarea", f, re.I) and not re.search(r'type=["\']?search|role=["\']?search', f, re.I):
            return True
    return bool(re.search(r"wpcf7|wpforms|gform_wrapper|hbspt\.forms|formidable|ninja-forms|elementor-form"
                          r"|typeform\.com|jotform", html, re.I))


def _liens_contact(html, base):
    vus = []
    for href, texte in re.findall(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>([\s\S]{0,200}?)</a>', html, re.I):
        cible = _norm(href + " " + re.sub(r"<[^>]+>", " ", texte)).replace(" ", "-")
        if any(m in cible for m in MOTS_CONTACT) and not href.startswith(("mailto:", "tel:", "javascript:")):
            url = urllib.parse.urljoin(base, href)
            if _racine(url) == _racine(base) and url not in vus:
                vus.append(url)
    # contact / recrutement en premier, mentions légales en dernier
    return sorted(vus, key=lambda u: next((i for i, m in enumerate(MOTS_CONTACT) if m in u.lower()), 99))


def explorer_site(site, pages_max=6):
    """{"site", "email", "formulaire"} : la meilleure adresse trouvée et la page du formulaire de contact."""
    res = {"site": site, "email": "", "formulaire": ""}
    if not site:
        return res
    site = site if site.startswith("http") else "https://" + site
    try:
        accueil, site_final = _lire(site)
    except Exception:
        return res
    res["site"] = site_final
    dom = _racine(site_final)
    a_voir = _liens_contact(accueil, site_final)
    a_voir += [urllib.parse.urljoin(site_final, p) for p in PAGES_CLASSIQUES]
    trouvees = _adresses(accueil, dom)
    vues = {site_final}
    for url in a_voir:
        if len(vues) > pages_max:
            break
        if url in vues:
            continue
        vues.add(url)
        try:
            page, _ = _lire(url)
        except Exception:
            continue
        trouvees += _adresses(page, dom)
        if not res["formulaire"] and _a_un_formulaire(page):
            res["formulaire"] = url.split("?")[0]
    if not res["formulaire"] and _a_un_formulaire(accueil):
        res["formulaire"] = site_final
    if trouvees:
        # on préfère recrutement@ / rh@ / jobs@ / contact@, puis l'adresse du domaine de l'entreprise
        trouvees.sort(key=lambda m: (next((i for i, g in enumerate(("recrutement", "rh", "jobs", "carriere",
                                                                    "contact")) if m.startswith(g)), 9),
                                     domaine(m) in GRAND_PUBLIC))
        res["email"] = trouvees[0]
    return res
