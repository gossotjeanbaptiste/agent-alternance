"""Assistant de premier lancement : import d'une installation existante, deuxième PC (tour) ou non,
messagerie, La Bonne Alternance (villes), profil et signature, CV.

L'assistant s'affiche tant que config.json n'existe pas ou contient "assistant_a_faire": true
(installation neuve) ; il écrit les réponses dans config.json et alternance/donnees/config_alternance.json
(ou %APPDATA%\\LMAgent pour la version installée) et met à jour les copies en mémoire.
"""
import json
import shutil
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from werkzeug.utils import secure_filename

import chemins  # noqa: F401
import commun
import emplacements
import reglages

TAILLE_CV_MAX = 10 * 1024 * 1024
EXTENSIONS_CV = {".pdf", ".doc", ".docx", ".odt"}
GEO = "https://geo.api.gouv.fr/communes?"


# --- lecture / écriture des configs --------------------------------------------------------------
def _lire(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def config_agent():
    """config.json actuel, ou une config neuve (ce PC seulement) tirée du modèle d'exemple."""
    c = _lire(emplacements.config_agent())
    if c is not None:
        return c
    c = _lire(emplacements.RESSOURCES / "config.example.json") or {}
    c.update(utiliser_tour=False, serveurs=[{"nom": "ce PC", "url": "local"}], assistant_a_faire=True)
    return c


def _ecrire_agent(modifs):
    c = config_agent()
    for chemin, v in modifs.items():
        reglages.ecrire_chemin(c, chemin, v)
    f = emplacements.config_agent()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commun.agent.CONFIG.update(c)


def _ecrire_alternance(modifs):
    f = commun.donnees.chemin("config_alternance.json")
    c = _lire(f) or {}
    for chemin, v in modifs.items():
        reglages.ecrire_chemin(c, chemin, v)
    f.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commun.CFG.clear()
    commun.CFG.update(c)


def a_faire():
    """Vrai tant que l'assistant n'est pas terminé (installation neuve)."""
    c = _lire(emplacements.config_agent())
    return c is None or bool(c.get("assistant_a_faire"))


# --- état affiché ---------------------------------------------------------------------------------
def lm_studio_present():
    return Path(commun.agent.LMS).exists() or bool(shutil.which("lms"))


def etat():
    cfg, ag = commun.CFG, config_agent()
    m = (cfg.get("messagerie") or {})
    lba = cfg.get("la_bonne_alternance") or {}
    tour = ag.get("tour") or {}
    profil = commun.donnees.chemin("profil.md")
    return {
        "lm_studio": lm_studio_present(),
        "ancienne": str(chercher_ancienne_installation() or ""),
        "depuis_le_code": emplacements.DEPUIS_LE_CODE,
        "utiliser_tour": commun.agent.utiliser_tour(ag),
        "tour_url": next((s.get("url") for s in ag.get("serveurs") or [] if s.get("url") != "local"), ""),
        "tour_mac": tour.get("mac", "") if tour.get("mac") != "AA:BB:CC:DD:EE:FF" else "",
        "tour_ssh": tour.get("ssh", "") if "nom-de-la-tour" not in tour.get("ssh", "") else "",
        "messagerie": m.get("type", "outlook"),
        "imap_adresse": (m.get("imap") or {}).get("adresse", ""),
        "imap_mdp_defini": bool((m.get("imap") or {}).get("mot_de_passe_app")),
        "jeton_defini": bool(lba.get("jeton_api")),
        "villes": "\n".join(v.get("nom", "") for v in lba.get("villes") or []),
        "rayon": lba.get("rayon_km", 25),
        "profil": profil.read_text(encoding="utf-8") if profil.exists() else "",
        "signature": cfg.get("signature_formulaire") or {},
        "domaines": "\n".join(cfg.get("domaines_ignores") or []),
        "cv": [Path(p).name for p in cfg.get("pieces_jointes") or []],
    }


# --- import d'une installation existante ---------------------------------------------------------
def _config_dans(base):
    for c in (base / "alternance" / "donnees" / "config_alternance.json", base / "alternance" / "config_alternance.json",
              base / "donnees" / "config_alternance.json"):
        if c.exists():
            return c
    return None


def chercher_ancienne_installation(chemin=None):
    """Dossier d'une installation existante (copie du projet lancée depuis le code), à importer."""
    candidats = [Path(chemin).expanduser()] if chemin else [Path.home() / "Documents" / "lm_agent"]
    for base in candidats:
        if base.resolve() != emplacements.BASE.resolve() and _config_dans(base):
            return base
    return None


def importer(chemin=None):
    """Copie config, données, export LinkedIn et pièces jointes d'une installation existante.
    Le compte de l'interface n'est pas importé (celui qui vient d'être créé reste). Renvoie (ok, message)."""
    base = chercher_ancienne_installation(chemin)
    if not base:
        return False, "Aucune installation trouvée à cet endroit (il faut un dossier contenant alternance/donnees)."
    source_donnees = _config_dans(base).parent
    dest = commun.donnees.DONNEES
    copies = []
    for nom in commun.donnees.PERSONNELS:
        if (source_donnees / nom).exists():
            shutil.copy2(source_donnees / nom, dest / nom)
            copies.append(nom)
    for sous in ("linkedin", "pieces_jointes"):
        if (base / sous).is_dir():
            shutil.copytree(base / sous, emplacements.dossier(sous), dirs_exist_ok=True)
            copies.append(sous + "/")
    ancienne_cfg = _lire(base / "config.json")
    if ancienne_cfg is not None:
        ancienne_cfg["assistant_a_faire"] = False
        emplacements.config_agent().parent.mkdir(parents=True, exist_ok=True)
        emplacements.config_agent().write_text(json.dumps(ancienne_cfg, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
        commun.agent.CONFIG.update(ancienne_cfg)
        copies.append("config.json")
    # chemins de l'ancienne installation -> nouveaux emplacements
    cfg = _lire(dest / "config_alternance.json") or {}
    ancien = str(base.resolve()).lower()
    if str(commun.P(cfg.get("tableau_suivi") or "")).lower().startswith(ancien):
        cfg["tableau_suivi"] = ""          # = suivi_alternance.xlsx du nouveau dossier de données
    pj = []
    for p in cfg.get("pieces_jointes") or []:
        p_abs = commun.P(p)
        pj.append(str(emplacements.dossier("pieces_jointes") / p_abs.name)
                  if str(p_abs).lower().startswith(ancien) else p)
    cfg["pieces_jointes"] = pj
    (dest / "config_alternance.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commun.CFG.clear()
    commun.CFG.update(cfg)
    return True, f"Importé depuis {base} : {', '.join(copies)}."


# --- étapes ---------------------------------------------------------------------------------------
def etape_tour(d):
    if not d.get("utiliser"):
        _ecrire_agent({"utiliser_tour": False, "serveurs": [{"nom": "ce PC", "url": "local"}]})
        return True, "L'IA tournera sur ce PC."
    url = str(d.get("url") or "").strip().rstrip("/")
    if not url.startswith("http"):
        return False, "Indique l'adresse du serveur LM Studio de la tour (ex. http://nom-de-la-tour:1236/v1)."
    _ecrire_agent({"utiliser_tour": True, "serveurs": [{"nom": "tour", "url": url, "reveil": True},
                                                       {"nom": "ce PC", "url": "local"}],
                   "tour.url_lmstudio": url, "tour.mac": str(d.get("mac") or "").strip(),
                   "tour.ssh": str(d.get("ssh") or "").strip()})
    return True, "Tour enregistrée (ce PC sert de secours). Détails dans Paramètres et GUIDE_TOUR.md."


def etape_messagerie(d):
    typ = str(d.get("type") or "outlook")
    if typ not in ("outlook", "imap"):
        return False, "Messagerie inconnue."
    modifs = {"messagerie.type": typ}
    if typ == "imap":
        adresse = str(d.get("adresse") or "").strip()
        mdp = str(d.get("mot_de_passe_app") or "").strip()
        if "@" not in adresse:
            return False, "Indique ton adresse mail."
        if not mdp and not ((commun.CFG.get("messagerie") or {}).get("imap") or {}).get("mot_de_passe_app"):
            return False, "Indique le mot de passe d'application (Gmail : myaccount.google.com/apppasswords)."
        modifs.update({"messagerie.imap.serveur": str(d.get("serveur") or "imap.gmail.com").strip(),
                       "messagerie.imap.port": 993, "messagerie.imap.adresse": adresse})
        if mdp:
            modifs["messagerie.imap.mot_de_passe_app"] = mdp
    _ecrire_alternance(modifs)
    return True, "Messagerie enregistrée."


def coordonnees(nom):
    """{"nom", "lat", "lon"} d'une commune française (geo.api.gouv.fr), ou None."""
    q = urllib.parse.urlencode({"nom": nom, "fields": "nom,centre,population", "boost": "population", "limit": 1})
    with urllib.request.urlopen(GEO + q, timeout=10) as r:
        res = json.loads(r.read())
    if not res or not (res[0].get("centre") or {}).get("coordinates"):
        return None
    lon, lat = res[0]["centre"]["coordinates"]
    return {"nom": res[0]["nom"], "lat": round(lat, 4), "lon": round(lon, 4)}


def _cle(nom):
    """Nom de ville comparable : minuscules, sans accents ni tirets."""
    s = unicodedata.normalize("NFD", str(nom)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace("'", " ").split())


def _ville_saisie(ligne):
    """« Nom ; latitude ; longitude » saisi à la main, ou None."""
    morceaux = [m.strip() for m in ligne.split(";")]
    if len(morceaux) != 3 or not morceaux[0]:
        return None
    try:
        lat, lon = float(morceaux[1].replace(",", ".")), float(morceaux[2].replace(",", "."))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {"nom": morceaux[0], "lat": round(lat, 4), "lon": round(lon, 4)}


def _villes_connues():
    """Villes déjà présentes dans la config (importée ou précédente), par nom comparable."""
    c = _lire(commun.donnees.chemin("config_alternance.json")) or {}
    lba = c.get("la_bonne_alternance") or {}
    connues = {}
    for v in (lba.get("villes") or []) + [lba.get("centre") or {}]:
        if isinstance(v, dict) and v.get("nom") and v.get("lat") is not None and v.get("lon") is not None:
            connues.setdefault(_cle(v["nom"]), {"nom": v["nom"], "lat": v["lat"], "lon": v["lon"]})
    return connues


def etape_lba(d):
    noms = [n.strip() for n in str(d.get("villes") or "").splitlines() if n.strip()]
    if not noms:
        return False, "Indique au moins une ville (une par ligne), la première sert de référence."
    connues = _villes_connues()
    villes, inconnues = [], []
    try:
        for n in noms:
            v = _ville_saisie(n) or connues.get(_cle(n)) or coordonnees(n)
            (villes.append(v) if v else inconnues.append(n))
    except Exception as e:
        return False, f"Recherche des villes impossible ({e}) : vérifie ta connexion Internet."
    if inconnues:
        return False, ("Villes introuvables : " + ", ".join(inconnues)
                       + ". Corrige le nom, ou indique la position à la main : « Nom ; latitude ; longitude ».")
    try:
        rayon = int(d.get("rayon") or 25)
    except ValueError:
        return False, "Rayon : nombre de kilomètres attendu."
    modifs = {"la_bonne_alternance.villes": villes, "la_bonne_alternance.centre": villes[0],
              "la_bonne_alternance.villes_prioritaires": [villes[0]["nom"]], "la_bonne_alternance.rayon_km": rayon}
    jeton = str(d.get("jeton") or "").strip()
    if jeton:
        modifs["la_bonne_alternance.jeton_api"] = jeton
    _ecrire_alternance(modifs)
    return True, f"{len(villes)} ville(s) enregistrée(s)."


def etape_profil(d):
    texte = str(d.get("profil") or "").strip()
    if len(texte) < 50:
        return False, "Profil trop court : décris ta formation, le poste visé, tes projets (c'est ce qui guide le modèle)."
    sig = d.get("signature") or {}
    sig = {k: str(sig.get(k) or "").strip()[:300] for k in ("nom", "titre", "telephone", "email", "linkedin",
                                                           "portfolio", "github")}
    if not sig["nom"]:
        return False, "Indique ton nom (signature)."
    commun.donnees.chemin("profil.md").write_text(texte + "\n", encoding="utf-8")
    domaines = [x.strip().lower() for x in str(d.get("domaines") or "").splitlines() if x.strip()]
    _ecrire_alternance({"signature_formulaire": sig, "debut_signature": sig["nom"], "domaines_ignores": domaines})
    return True, "Profil et signature enregistrés."


def etape_cv(fichier):
    """Fichier envoyé depuis le navigateur (werkzeug FileStorage) -> dossier des pièces jointes."""
    if fichier is None or not fichier.filename:
        return False, "Choisis un fichier."
    nom = secure_filename(fichier.filename) or "cv.pdf"
    if Path(nom).suffix.lower() not in EXTENSIONS_CV:
        return False, "Formats acceptés : PDF, DOC, DOCX, ODT."
    contenu = fichier.read(TAILLE_CV_MAX + 1)
    if len(contenu) > TAILLE_CV_MAX:
        return False, "Fichier trop gros (10 Mo maximum)."
    dossier = emplacements.dossier("pieces_jointes")
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / nom).write_bytes(contenu)
    pj = [p for p in commun.CFG.get("pieces_jointes") or [] if Path(p).name != nom] + [str(dossier / nom)]
    _ecrire_alternance({"pieces_jointes": pj})
    return True, f"{nom} ajouté aux pièces jointes."


def terminer():
    _ecrire_agent({"assistant_a_faire": False})
    return True, "Configuration terminée."


ETAPES = {"tour": etape_tour, "messagerie": etape_messagerie, "lba": etape_lba, "profil": etape_profil,
          "terminer": lambda d: terminer(), "importer": lambda d: importer(d.get("chemin") or None)}
