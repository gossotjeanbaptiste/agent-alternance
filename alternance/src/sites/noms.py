"""Le nom d'une entreprise : ses mots distinctifs, un domaine qui lui ressemble, la ville de son adresse."""
import re
import unicodedata

import reglages
from .pages import _racine

# modifiable dans la page Paramètres (section « Sites des entreprises »)
ANNUAIRES = tuple(reglages.valeur("sites.annuaires"))          # sites qui parlent de l'entreprise sans être le sien
FORMES = {"sarl", "sas", "sasu", "eurl", "sa", "sci", "snc", "groupe", "group", "france", "societe", "soc",
          "ste", "et", "de", "des", "du", "la", "le", "les", "services", "service", "informatique"}
JURIDIQUE = {"sarl", "sas", "sasu", "eurl", "sa", "sci", "snc", "soc", "ste", "societe", "et", "de", "des",
             "du", "la", "le", "les"}


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


def _mots(nom):
    """Mots qui distinguent l'entreprise (sans « SARL », « France », « Services »…)."""
    mots = [m for m in _mots_nom(nom) if m not in FORMES]
    return [m for m in mots if len(m) >= 3] or [m for m in mots if len(m) >= 2]


def ressemble(nom, url):
    """Vrai si le nom de domaine correspond au nom de l'entreprise (lambert-morel.com ↔ Lambert Morel)."""
    dom = _racine(url)
    if not dom or any(a in dom for a in ANNUAIRES):
        return False
    base = re.sub(r"[^a-z0-9]", "", dom.rsplit(".", 1)[0])
    mots = _mots(nom)
    colle = "".join(mots)
    if len(colle) >= 4 and colle in base:
        return True
    return bool(mots) and all(m in base for m in mots)


def _repere_lieu(lieu):
    """(code postal, ville) tirés d'une adresse « 12 rue X 69000 Lyon »."""
    cp = re.search(r"\b(\d{5})\b", lieu or "")
    ville = re.sub(r"\d{5}|cedex", " ", (lieu or "").split(",")[-1], flags=re.I)
    if cp:
        ville = (lieu or "")[cp.end():] or ville
    return (cp.group(1) if cp else ""), _norm(ville).replace(" ", "")
