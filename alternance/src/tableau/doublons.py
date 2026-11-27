"""Entreprise déjà dans le tableau ? Même SIRET, même domaine mail, ou même nom ET même ville
(plusieurs établissements du même nom à des adresses différentes sont permis)."""
from mails import adresses, domaine
from .texte import cle_lieu, norm


def deja_contactee(o, noms, domaines, sirets):
    """Vrai si l'entreprise est déjà dans le tableau, même écrite un peu différemment
    (ex. « Pixelo Lyon Est » vs « PIXELO », « Brio Villeurbanne » vs « BRIO »).
    noms : {nom normalisé: villes (cle_lieu)} (un simple ensemble de noms est aussi accepté).
    Même nom mais ville différente = autre établissement, pas un doublon ; si l'une des deux villes est
    inconnue, on considère que c'est la même entreprise (prudence)."""
    if not isinstance(noms, dict):
        noms = {k: {""} for k in noms}
    n = norm(o["entreprise"])
    if not n:
        return True
    if o.get("siret") and o["siret"] in sirets:
        return True
    if any(domaine(a) in domaines for a in adresses(o.get("email"))):   # plusieurs adresses possibles
        return True
    lieu = cle_lieu(o.get("lieu"))

    def meme_lieu(villes):
        return not lieu or "" in villes or lieu in villes
    if n in noms and meme_lieu(noms[n]):
        return True
    return any(len(k) >= 4 and (k in n or n in k) and meme_lieu(v) for k, v in noms.items() if len(n) >= 4)


def retenir(noms, o):
    """Ajoute l'entreprise o à {nom: villes} (pour ne pas la reprendre deux fois)."""
    noms.setdefault(norm(o["entreprise"]), set()).add(cle_lieu(o.get("lieu")))
