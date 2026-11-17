"""Valeurs du tableau rendues comparables : nom d'entreprise, date, ville d'une adresse."""
import re
import unicodedata
from datetime import date, datetime


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(sas|sarl|sa|eurl|sasu|groupe|group)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def ville(lieu):
    """Ville d'une adresse, lisible : « 12 RUE X 69003 LYON CEDEX 03 » -> « Lyon », « Lyon (69) » -> « Lyon ».
    "" si l'adresse est inconnue."""
    s = str(lieu or "")
    cp = list(re.finditer(r"\b\d{5}\b", s))
    if cp:
        avant, apres = s[:cp[-1].start()], s[cp[-1].end():]
        if re.search(r"[A-Za-zÀ-ÿ]", apres):      # « … 69003 Lyon » : la ville suit le code postal
            s = apres
        else:                                       # « … Lyon 69003 » : dernier mot avant le code postal
            mots = avant.replace(",", " ").split()
            s = mots[-1] if mots else ""
    s = re.sub(r"\bcedex\b", "", s, flags=re.I)
    s = re.sub(r"[^A-Za-zÀ-ÿŒœ' -]", " ", s)       # chiffres, parenthèses, virgules
    s = " ".join(s.split()).strip(" -'")
    if not (s.isupper() or s.islower()):   # déjà écrite en minuscules et majuscules : on n'y touche pas
        return s
    petits = {"les", "lès", "sur", "sous", "en", "de", "du", "des", "la", "le", "aux", "l", "d"}
    morceaux = re.split(r"([ '-])", s.lower())   # « l'isle-d'abeau » -> l ' isle - d ' abeau
    return "".join(m if (m in petits and i) or m in " '-" else m.capitalize() for i, m in enumerate(morceaux))


def cle_lieu(lieu):
    """Ville d'une adresse, comparable : « 12 rue X 69003 Lyon Cedex » -> « lyon », « Lyon (69) » -> « lyon ».
    "" si l'adresse est inconnue."""
    s = unicodedata.normalize("NFKD", ville(lieu)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)
