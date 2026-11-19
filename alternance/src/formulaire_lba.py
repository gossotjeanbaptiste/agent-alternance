"""Formulaire « Candidature simplifiée » de La Bonne Alternance prérempli (bouton « Ouvrir le formulaire prérempli »
de la page À postuler) : ce module prépare les données ; formulaire_lba_chrome.py les met dans le formulaire.
Identité (signature des formulaires), « Ma recherche d'alternance » (réglages de la section « Formulaire La Bonne
Alternance prérempli »), message (la lettre), réponses aux questions, CV. Rien n'est jamais envoyé par LMAgent."""
import re
from pathlib import Path

import commun
import reglages

TAILLE_CV_MAX = 3 * 1024 * 1024        # limite du site
FORMATS_CV = (".pdf", ".docx", ".doc")
LIMITE_RECHERCHE = 200                 # « La taille des champs est limitée à 200 caractères »
# question du site -> clé des réponses de LMAgent (reglages.QUESTIONS), reconnue à des mots de son intitulé
MOTS_QUESTIONS = {"motivations": ("pourquoi", "rejoindre", "motivation"), "missions": ("mission",),
                  "experiences": ("expérience", "experience", "stage")}
SITUATIONS = {"déjà inscrit(e) en formation": 0, "pas encore inscrit(e) en formation": 1}


def nom_et_prenom(complet):
    """(nom, prénom) depuis « Prénom NOM » : les mots en majuscules forment le nom, sinon le dernier mot."""
    mots = str(complet or "").split()
    nom = [m for m in mots if m.isupper() and len(m) > 1]
    if not nom and mots:
        nom = mots[-1:]
    prenom = [m for m in mots if m not in nom]
    return " ".join(nom), " ".join(prenom)


def _cv_valide(p):
    return p.suffix.lower() in FORMATS_CV and p.is_file() and p.stat().st_size <= TAILLE_CV_MAX


def choisir_cv(chemins):
    """Le CV parmi les pièces jointes : PDF ou Word de moins de 3 Mo, celui dont le nom contient « cv » d'abord."""
    ok = [Path(c) for c in chemins if _cv_valide(Path(c))]
    ok.sort(key=lambda p: (not re.search(r"(^|[^a-z])cv([^a-z]|$)", p.stem.lower()), p.suffix.lower() != ".pdf"))
    return ok[0] if ok else None


def cv_du_formulaire():
    """(CV à joindre ou None, remarque ou "") : le fichier du réglage (chemin, ou nom dans pieces_jointes/),
    sinon le CV des pièces jointes des candidatures."""
    voulu = str(reglages.valeur("la_bonne_alternance.cv") or "").strip()
    if voulu:
        p = commun.P(voulu)
        if not p.is_file():
            p = commun.donnees.emplacements.dossier("pieces_jointes") / Path(voulu).name
        if _cv_valide(p):
            return p, ""
        remarque = f"le CV des paramètres ({voulu}) est introuvable, trop gros (3 Mo au plus) ou pas en PDF / Word"
        return choisir_cv(commun.pieces_jointes()), remarque
    return choisir_cv(commun.pieces_jointes()), ""


def cv_pour_le_navigateur(cv):
    """{"nom", "type", "contenu" (base64)} : le CV tel que remplir.js le joint au formulaire (None sans CV)."""
    import base64
    if not cv:
        return None
    p = Path(cv)
    typ = {".pdf": "application/pdf", ".doc": "application/msword",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(p.suffix.lower(), "")
    return {"nom": p.name, "type": typ, "contenu": base64.b64encode(p.read_bytes()).decode()}


def cle_question(intitule):
    """Clé de la réponse LMAgent qui correspond à une question du site (None si aucune)."""
    t = str(intitule or "").lower()
    return next((cle for cle, mots in MOTS_QUESTIONS.items() if any(m in t for m in mots)), None)


def champs(lettre, reponses):
    """Ce que le formulaire recevra (dictionnaire passé tel quel au JavaScript de remplissage)."""
    s = commun.CFG.get("signature_formulaire") or {}
    nom, prenom = nom_et_prenom(s.get("nom"))
    val = reglages.valeur
    return {"applicant_last_name": nom, "applicant_first_name": prenom,
            "applicant_email": str(s.get("email") or "").strip(),
            "applicant_phone": re.sub(r"[^\d+]", "", str(s.get("telephone") or "")),
            "applicant_message": str(lettre or "").strip(),
            "situation": SITUATIONS.get(val("la_bonne_alternance.situation")),
            "applicant_formation_description": str(val("la_bonne_alternance.formation") or "").strip()[:LIMITE_RECHERCHE],
            "applicant_rythm_description": str(val("la_bonne_alternance.rythme") or "").strip()[:LIMITE_RECHERCHE],
            "duree": str(val("la_bonne_alternance.duree_contrat") or "").strip(),
            "debut": [str(d).strip() for d in (val("la_bonne_alternance.debut_contrat") or []) if str(d).strip()],
            "reponses": {cle: str(texte or "").strip() for cle, texte in (reponses or {}).items() if cle != "lettre"}}
