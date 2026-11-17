"""Sur le site d'une entreprise : pages de contact, adresses mail affichées (même masquées), formulaire de contact."""
import html as html_lib
import re
import urllib.parse

import pays
import reglages
import sites
from mails import DOMAINES_PERSO, domaine
from .noms import _norm
from .pages import _racine

# modifiables dans la page Paramètres (section « Sites des entreprises »)
GRAND_PUBLIC = tuple(DOMAINES_PERSO)                             # messageries grand public (acceptées sur le site même)
MOTS_CONTACT = tuple(reglages.valeur("sites.mots_contact"))
PAGES_CLASSIQUES = tuple(reglages.valeur("sites.pages_classiques"))
PREFERES = ("recrutement", "rh", "jobs", "carriere", "contact")   # adresses préférées, dans l'ordre


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


def _parcourir(accueil, site_final, pages_max):
    """Pages de contact du site (liens, puis adresses classiques) : (pages lues, adresses trouvées, formulaire)."""
    dom = _racine(site_final)
    lues, trouvees, formulaire = [accueil], _adresses(accueil, dom), ""
    a_voir = _liens_contact(accueil, site_final) + [urllib.parse.urljoin(site_final, p) for p in PAGES_CLASSIQUES]
    vues = {site_final}
    for url in a_voir:
        if len(vues) > (pages_max or int(reglages.valeur("sites.pages_max"))):
            break
        if url in vues:
            continue
        vues.add(url)
        try:
            page, _ = sites._lire(url)
        except Exception:
            continue
        lues.append(page)
        trouvees += _adresses(page, dom)
        if not formulaire and _a_un_formulaire(page):
            formulaire = url.split("?")[0]
    if not formulaire and _a_un_formulaire(accueil):
        formulaire = site_final
    return lues, trouvees, formulaire


def explorer_site(site, pages_max=None, lieu=""):
    """{"site", "email", "formulaire", "ecarte"} : la meilleure adresse trouvée et la page du formulaire de contact.
    Site d'une entreprise hors de France : rien n'est gardé, "ecarte" donne la raison."""
    res = {"site": site, "email": "", "formulaire": "", "ecarte": ""}
    if not site:
        return res
    site = site if site.startswith("http") else "https://" + site
    try:
        accueil, site_final = sites._lire(site)
    except Exception:
        return res
    res["site"] = site_final
    if sites.verifier_france() and pays.pays_de_l_extension(site_final) not in ("", "France"):
        return {**res, "site": "", "ecarte": pays.verdict(site_final, [], lieu)[1] + f" : {site_final}"}
    lues, trouvees, res["formulaire"] = _parcourir(accueil, site_final, pages_max)
    en_france, raison = sites.site_en_france(site_final, lieu, lues)
    if not en_france:   # entreprise d'un autre pays : ni son adresse ni son formulaire
        return {"site": "", "email": "", "formulaire": "", "ecarte": f"{raison} : {site_final}"}
    if trouvees:
        # on préfère recrutement@ / rh@ / jobs@ / contact@, puis l'adresse du domaine de l'entreprise
        trouvees.sort(key=lambda m: (next((i for i, g in enumerate(PREFERES) if m.startswith(g)), 9),
                                     domaine(m) in GRAND_PUBLIC))
        res["email"] = trouvees[0]
    return res
