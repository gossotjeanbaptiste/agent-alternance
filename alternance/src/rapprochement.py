"""À quelle candidature du tableau correspond un mail reçu ?

Par ordre de sûreté :
1. même adresse que celle du tableau ;
2. même domaine (s'il est propre à cette entreprise dans le tableau, et pas une messagerie grand public) ;
3. le nom du domaine de l'entreprise est l'une des parties du domaine de l'expéditeur : outil de support ou de
   recrutement à son nom (« comptanova.com » -> support@comptanova.on.crisp.email) ;
4. un mot distinctif du nom de l'entreprise est dans l'adresse de l'expéditeur, souvent une adresse personnelle
   (« Forgeval Dev » -> marc.forgeval@gmail.com). Ce mot doit faire au moins 5 lettres, ne pas être un mot courant
   et n'appartenir à aucune autre entreprise du tableau.
"""
import re
from collections import Counter

from mails import DOMAINES_PERSO, domaine
from tableau import norm

MOTS_COURANTS = {"france", "groupe", "group", "services", "service", "solutions", "conseil", "consulting",
                 "informatique", "digital", "numerique", "technologies", "technology", "systemes", "systems",
                 "agence", "studio", "societe", "entreprise", "international", "europe", "software", "logiciels",
                 "reseaux", "reseau", "sante", "formation", "industrie", "partners", "associes", "gestion",
                 "developpement", "consultants", "ingenierie", "mairie", "centre", "region", "ville"}


def mots_du_nom(entreprise):
    """Mots d'au moins 5 lettres du nom, sans accents (« Forgeval Dev » -> [forgeval])."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(entreprise or "")).encode("ascii", "ignore").decode().lower()
    return [m for m in re.split(r"[^a-z0-9]+", s) if len(m) >= 5 and m not in MOTS_COURANTS]


def mots_distinctifs(entreprises):
    """{entreprise normalisée: mots qui n'appartiennent qu'à elle dans le tableau}."""
    par_entreprise = {norm(e): set(mots_du_nom(e)) for e in entreprises if e}
    compte = Counter(m for mots in par_entreprise.values() for m in mots)
    return {e: {m for m in mots if compte[m] == 1} for e, mots in par_entreprise.items()}


def _sans_accents(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def _domaine_du_site(site):
    """« https://www.forgeval-dev.fr/contact » -> « forgeval-dev.fr »."""
    m = re.match(r"(?:https?://)?(?:www\.)?([^/\s:]+)", str(site or "").strip().lower())
    return m.group(1) if m and "." in m.group(1) else ""


def preuves_dans_le_mail(corps, entreprise, adresse="", lieu="", telephone="", site=""):
    """Preuves, dans le texte du mail (signature surtout), qu'il vient bien de cette entreprise :
    son domaine (adresse ou site), son numéro de téléphone, ou son nom accompagné de son code postal / sa ville.
    Renvoie la liste des preuves trouvées (vide si aucune)."""
    from tableau import cle_lieu
    texte = _sans_accents(corps)
    preuves = []
    domaines = {d for d in (domaine(adresse) if adresse else "", _domaine_du_site(site))
                if d and d not in DOMAINES_PERSO}
    for d in sorted(domaines):
        # www.forgeval-dev.fr ou contact@forgeval-dev.fr oui ; notre-forgeval-dev.fr.example non
        if re.search(rf"(?<![a-z0-9-]){re.escape(d)}(?!\.?[a-z0-9-])", texte):
            preuves.append(f"domaine {d}")
    chiffres = re.sub(r"\D", "", str(telephone or ""))
    if len(chiffres) >= 9:
        for numero in re.findall(r"(?:\+|00)?\d[\d .()-]{7,}\d", texte):
            n = re.sub(r"\D", "", numero)
            if len(n) >= 9 and n[-9:] == chiffres[-9:]:
                preuves.append(f"téléphone {telephone}")
                break
    nom = re.sub(r"[^a-z0-9]", "", _sans_accents(entreprise))
    if len(nom) >= 5 and nom in re.sub(r"[^a-z0-9]", "", texte):
        cp = re.search(r"\b\d{5}\b", str(lieu or ""))
        ville = cle_lieu(lieu)
        if cp and re.search(rf"\b{cp.group(0)}\b", texte):
            preuves.append(f"nom et code postal {cp.group(0)}")
        elif len(ville) >= 4 and ville in re.sub(r"[^a-z]", "", texte):
            preuves.append("nom et ville")
    return preuves


def correspond(expediteur, adresse, domaine_propre, distinctifs):
    """Vrai si le mail de expediteur répond à la candidature dont l'adresse du tableau est adresse.
    domaine_propre : le domaine de cette adresse n'appartient qu'à cette entreprise dans le tableau.
    distinctifs : mots distinctifs du nom de l'entreprise (mots_distinctifs)."""
    de = str(expediteur or "").strip().lower()
    if "@" not in de:
        return False
    adresse = str(adresse or "").strip().lower()
    if adresse and de == adresse:                                       # 1. même adresse
        return True
    dom_de = de.split("@")[-1]
    dom = domaine(adresse) if adresse else ""
    if dom and domaine_propre and dom not in DOMAINES_PERSO:
        if dom_de == dom:                                               # 2. même domaine
            return True
        base = dom.rsplit(".", 1)[0]          # comptanova.com -> comptanova ; forgeval-dev.fr -> forgeval-dev
        if len(base.replace("-", "")) >= 5 and base in dom_de.split(".")[:-1]:
            return True                                                 # 3. outil à son nom (….on.crisp.email)
    local = de.split("@")[0]
    return any(m in local for m in distinctifs)                         # 4. mot distinctif dans l'adresse
