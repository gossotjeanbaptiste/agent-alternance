"""Retrouver une entreprise sur La Bonne Alternance (candidature d'une autre source, ex. ta liste perso) : par son
SIRET, sinon par son nom, parmi les recruteurs autour de son adresse (coordonnées par la Base Adresse Nationale).
Gardée seulement si La Bonne Alternance lui transmet les candidatures (recipient_id) : sinon sa page n'est qu'une fiche."""
import json
import re
import urllib.parse
import urllib.request

from commun import CFG
from tableau import norm

API_ADRESSE = "https://api-adresse.data.gouv.fr/search/"
API_LBA = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
RAYON_KM = 1          # l'entreprise est à son adresse : un petit rayon suffit et garde la recherche rapide


def siret_de(*textes):
    """SIRET (14 chiffres) noté dans les notes ou les infos d'une ligne, ou ""."""
    for t in textes:
        if m := re.search(r"SIRET\s*:?\s*(\d{14})", str(t or "")):
            return m.group(1)
    return ""


def coordonnees(adresse):
    """(latitude, longitude) d'une adresse en France, ou None."""
    q = urllib.parse.urlencode({"q": adresse, "limit": 1})
    with urllib.request.urlopen(f"{API_ADRESSE}?{q}", timeout=20) as r:
        points = json.loads(r.read()).get("features") or []
    if not points:
        return None
    lon, lat = points[0]["geometry"]["coordinates"]
    return lat, lon


def _recruteurs(lat, lon, romes):
    c = CFG["la_bonne_alternance"]
    params = {"latitude": lat, "longitude": lon, "radius": RAYON_KM}
    if romes:
        params["romes"] = ",".join(romes)
    req = urllib.request.Request(f"{API_LBA}?{urllib.parse.urlencode(params)}",
                                 headers={"Authorization": f"Bearer {c['jeton_api']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return (data.get("jobs") or []) + (data.get("recruiters") or [])


def _meme_entreprise(item, entreprise, siret):
    wp = item.get("workplace") or {}
    if siret:
        return str(wp.get("siret") or "") == siret
    noms = {norm(wp.get(k)) for k in ("brand", "name", "legal_name")} - {""}
    return norm(entreprise) in noms


def trouver(entreprise, siret, adresse):
    """(fiche, raison) : fiche = {"lien", "activite"} si l'entreprise est sur La Bonne Alternance avec un formulaire,
    sinon None et la raison, à montrer à l'utilisateur."""
    c = CFG["la_bonne_alternance"]
    if not c.get("jeton_api"):
        return None, "pas de jeton API La Bonne Alternance (Paramètres)"
    if not adresse:
        return None, "adresse de l'entreprise inconnue"
    item = None
    try:
        point = coordonnees(adresse)
        if not point:
            return None, f"adresse introuvable ({adresse})"
        # d'abord parmi les recruteurs de tes métiers (codes ROME), puis parmi tous
        for romes in (c.get("codes_rome") or [], []):
            item = next((i for i in _recruteurs(*point, romes) if _meme_entreprise(i, entreprise, siret)), None)
            if item:
                break
    except Exception as e:
        return None, f"La Bonne Alternance ne répond pas ({e})"
    if not item:
        return None, "introuvable sur La Bonne Alternance"
    apply = item.get("apply") or {}
    if not apply.get("recipient_id") or not apply.get("url"):
        return None, "sur La Bonne Alternance, mais sans formulaire de candidature"
    naf = (((item.get("workplace") or {}).get("domain") or {}).get("naf") or {}).get("label") or ""
    return {"lien": apply["url"], "activite": naf}, ""
