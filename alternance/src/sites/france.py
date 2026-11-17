"""Site d'une entreprise en France ? (réglage « sites.verifier_france », preuves dans pays.py)"""
import urllib.parse

import pays
import reglages
import sites


def verifier_france():
    return bool(reglages.valeur("sites.verifier_france"))


def site_en_france(url, lieu="", pages=()):
    """(en France ?, raison) : extension, sinon preuves dans les pages déjà lues, puis dans les pages
    « mentions légales / contact » du site si besoin. Toujours vrai si la vérification est désactivée."""
    if not verifier_france():
        return True, "vérification désactivée"
    ok, raison = pays.verdict(url, list(pages), lieu)
    if ok or pays.pays_de_l_extension(url):     # extension française ou étrangère : réponse sûre
        return ok, raison
    textes = list(pages)
    for chemin in ("/mentions-legales", "/mentions-legales/", "/contact", "/contact/"):
        try:
            page, final = sites._lire(urllib.parse.urljoin(url, chemin), 300_000)
        except Exception:
            continue
        if sites._racine(final) != sites._racine(url):
            continue
        textes.append(page)
        ok, raison = pays.verdict(url, textes, lieu)
        if ok:
            return ok, raison
    return ok, raison
