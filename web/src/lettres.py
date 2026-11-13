"""Lettres des candidatures « À postuler » (brouillons, mis en cache 5 min) et réponses du formulaire."""
import re
import time

import chemins  # noqa: F401

CACHE = {"quand": 0, "lettres": {}, "signature": "", "note": None}


def _outlook_ferme():
    """Vrai si la messagerie est l'Outlook classique et qu'il n'est pas lancé : la page ne l'ouvre pas
    (le lancer prend ~20 s, la page semblait ne pas répondre et il fallait cliquer deux fois)."""
    from messagerie import type_messagerie
    if type_messagerie() != "outlook":
        return False
    import outlook
    return not outlook._outlook_lance()


def lettres_et_signature():
    import reglages
    if time.time() - CACHE["quand"] > 60 * int(reglages.valeur("interface.cache_lettres_minutes")):
        import pythoncom
        import postuler
        ferme = _outlook_ferme()
        pythoncom.CoInitialize()  # Outlook (COM) depuis un fil du serveur web
        try:
            CACHE["lettres"] = postuler.lettres_des_brouillons(lire_messagerie=not ferme)
            CACHE["signature"] = postuler.signature()
        finally:
            pythoncom.CoUninitialize()
        CACHE["note"] = ("Outlook classique fermé : les lettres des candidatures par mail ne sont pas affichées "
                         "(ouvre Outlook puis recharge la page)." if ferme else None)
        if not ferme:  # Outlook fermé : pas de cache, il sera lu dès qu'il sera ouvert
            CACHE["quand"] = time.time()
    return CACHE["lettres"], CACHE["signature"]


def supprimer_brouillons(adresse):
    """Met à la corbeille les brouillons adressés à cette adresse ; renvoie un message pour l'interface."""
    import pythoncom
    from messagerie import nom_messagerie, ouvrir
    pythoncom.CoInitialize()
    try:
        n = ouvrir().supprimer_brouillons(adresse)
    except Exception as e:
        return f"Brouillon non supprimé ({e}) : supprime-le à la main dans {nom_messagerie()}."
    finally:
        pythoncom.CoUninitialize()
    CACHE["quand"] = 0  # la liste des lettres a changé
    return f"Brouillon mis à la corbeille de {nom_messagerie()}." if n else "Aucun brouillon trouvé pour cette adresse."


def site_ou_recherche(l):
    """(site de l'entreprise ou "", recherche Google sur son nom et sa ville).
    Site : celui noté par la recherche (« Site : … » dans Notes), sinon le domaine de son adresse mail
    (sauf messageries grand public comme gmail.com)."""
    from urllib.parse import quote_plus
    from mails import DOMAINES_PERSO, domaine
    m = re.search(r"Site : (\S+)", str(l.get("Notes") or ""))
    site = m.group(1) if m else ""
    if not site:
        d = domaine(str(l.get("Email") or "").strip().lower())
        if d and d not in DOMAINES_PERSO and re.search(r"\.[a-z]{2,}$", d):
            site = "https://" + d
    lieu = str(l.get("Lieu") or "")
    ville = re.split(r"\b\d{5}\b", lieu)[-1].strip(" ,") or lieu
    return site, "https://www.google.com/search?q=" + quote_plus(f"{l.get('Entreprise') or ''} {ville}".strip())


def ajouter_lettres(lignes):
    """Ajoute à chaque ligne « _lettre » (lettre + signature) si un brouillon existe. Renvoie un message d'erreur ou None."""
    try:
        lettres, sig = lettres_et_signature()
    except Exception as e:
        return f"Lecture des lettres et brouillons impossible : {e}"
    import reponses
    deja = reponses.lire()
    for l in lignes:
        l["_mail"] = l.get("Statut") == "Brouillon"
        l["_lba"] = l.get("Statut") == "À postuler (La Bonne Alternance)"
        m = re.search(r"Formulaire : (\S+)", str(l.get("Notes") or ""))
        l["_formulaire"] = m.group(1) if m and l["_lba"] else ""  # 2e solution : le formulaire du site
        l["_reponses"] = reponses.en_liste(deja.get((l.get("Lien") or "").strip()) or {})
        l["_site"], l["_recherche"] = site_ou_recherche(l)
        if l["_mail"]:  # brouillon de mail : la signature est déjà celle de la messagerie
            l["_lettre"] = lettres.get(str(l.get("Email") or "").strip().lower())
            continue
        lettre = lettres.get((l.get("Lien") or "").strip())
        l["_lettre"] = (lettre + "\n\n" + sig) if lettre and sig else lettre
    for l in lignes:
        l["_ferme"] = bool(CACHE["note"])
    return CACHE["note"]
