"""Lecture d'un mail reçu au sujet d'une candidature faite en dehors de LM Agent : de quelle entreprise il parle,
pour quel poste, et ce qu'il dit (accusé de réception, refus, entretien…).

Formats connus lus directement (sans le modèle) : HelloWork, Indeed, LinkedIn, La Bonne Alternance.
Les autres (logiciel de recrutement d'une entreprise, cabinet…) sont confiés au modèle, seulement si le sujet
parle d'une candidature.
"""
import re
from dataclasses import dataclass

import modele
from mails import domaine
from . import classement


@dataclass
class Lu:
    """Ce qu'on a tiré d'un mail. type : automatique (accusé de réception) | entretien | disponibilites | positive | refus |
    transmise | autre | echec (candidature pas partie) ; plateforme : par où la candidature a été faite."""
    entreprise: str
    type: str
    plateforme: str
    poste: str = ""
    lieu: str = ""
    resume: str = ""


class ModeleInjoignable(Exception):
    """Le modèle n'a pas répondu : le mail sera relu au prochain passage."""


SUJET_CANDIDATURE = re.compile(r"candidat|postul|application|applied", re.I)
# mails de plateformes qui parlent de candidature sans en être une (relance pour postuler, offres, alertes)
PAS_UNE_CANDIDATURE = re.compile(r"finalis|déposez votre candidature|recrute au poste|offres? d.emploi|"
                                 r"nouvelles offres|alerte|votre compte", re.I)
# expéditeurs lus seulement par leurs formats connus (le reste : publicité, réseau, alertes)
PLATEFORMES = {"emails.hellowork.com": "HelloWork", "hellowork.com": "HelloWork", "indeed.com": "Indeed",
               "linkedin.com": "LinkedIn", "apprentissage.beta.gouv.fr": "La Bonne Alternance"}


SUJETS_LBA = re.compile(r"(Votre candidature chez|Votre candidature n'a pas pu être envoyée à|Suite donnée à votre "
                        r"candidature -|R[ée]ponse n[ée]gative de .+? à la candidature de) .+", re.I)


def nomme_l_entreprise(m):
    """Vrai pour un mail de La Bonne Alternance dont l'objet nomme l'entreprise : lu par son format (ailleurs.py),
    plus sûr que le rattachement d'après le contenu."""
    return _plateforme(m["de"]) == "La Bonne Alternance" and bool(SUJETS_LBA.match(m["sujet"].strip()))


def _plateforme(adresse):
    d = domaine(adresse)
    if d.startswith("reply."):           # reply.hellowork.com : le recruteur lui-même répond via HelloWork
        return ""
    return next((nom for dom, nom in PLATEFORMES.items() if d == dom or d.endswith("." + dom)), "")


def _propre(nom):
    """« Vortalis. » -> « Vortalis » ; « PIXELMONT FRANCE » -> « Pixelmont France »."""
    nom = re.sub(r"\s+", " ", str(nom or "")).strip(" .–-|")
    return nom.title() if nom.isupper() else nom


def _texte(corps):
    return re.sub(r"[\s‌͏\xad]+", " ", corps or "")


def lire_format_connu(m):
    """Lu, None (rien à voir avec une candidature envoyée), ou ... (format inconnu : à confier au modèle)."""
    sujet, plateforme = m["sujet"].strip(), _plateforme(m["de"])
    if plateforme == "HelloWork":
        if trouve := re.match(r"Votre candidature est arrivée chez (.+)$", sujet, re.I):
            poste = re.search(r"[\"“](.+?)[\"”] pour l'entreprise", _texte(m["corps"]))
            return Lu(_propre(trouve.group(1)), "automatique", "HelloWork", poste.group(1).strip() if poste else "")
        return None                       # « Finalisez votre candidature… », offres, conseils
    if plateforme == "Indeed":
        if trouve := re.match(r"Candidatures via Indeed : (.+?)(?: \| (.+))?$", sujet, re.I):
            return Lu(_propre(trouve.group(2)), "automatique", "Indeed", trouve.group(1).strip()) if trouve.group(2) else None
        if trouve := re.match(r"Des nouvelles de votre candidature pour (.+)$", sujet, re.I):
            return _classee(m, _propre(trouve.group(1)), "Indeed")
        return None
    if plateforme == "LinkedIn":
        if trouve := re.search(r"votre candidature a été envoyée à (.+)$", sujet, re.I):
            return Lu(_propre(trouve.group(1)), "automatique", "LinkedIn")
        return None                       # « déposez votre candidature maintenant… », réseau, alertes
    if plateforme == "La Bonne Alternance":
        if trouve := re.match(r"Votre candidature chez (.+)$", sujet, re.I):
            lieu = re.search(r"envoyée à .+?\](?:,)? (.+?)\. J", _texte(m["corps"]))
            return Lu(_propre(trouve.group(1)), "automatique", "La Bonne Alternance", "Candidature spontanée",
                      lieu.group(1).strip() if lieu else "")
        if trouve := re.match(r"Votre candidature n'a pas pu être envoyée à (.+)$", sujet, re.I):
            return Lu(_propre(trouve.group(1)), "echec", "La Bonne Alternance",
                      resume="La Bonne Alternance n'a pas pu envoyer la candidature (adresse de l'entreprise erronée)")
        if trouve := re.match(r"Suite donnée à votre candidature - (.+)$", sujet, re.I):
            return _classee(m, _propre(trouve.group(1)), "La Bonne Alternance")
        # refus envoyé par l'entreprise depuis La Bonne Alternance : la décision est dans l'objet, pas besoin du modèle
        if trouve := re.match(r"R[ée]ponse n[ée]gative de (.+?) à la candidature de .+$", sujet, re.I):
            return Lu(_propre(trouve.group(1)), "refus", "La Bonne Alternance",
                      resume="Réponse négative de l'entreprise, envoyée via La Bonne Alternance")
        return None
    if not SUJET_CANDIDATURE.search(sujet) or PAS_UNE_CANDIDATURE.search(sujet):
        return None
    return ...


def _classee(m, entreprise, plateforme):
    """Réponse transmise par une plateforme, entreprise connue : le modèle dit seulement ce qu'elle annonce."""
    typ, resume = classement.classer_reponse(entreprise, m["sujet"], m["corps"])
    if resume.startswith("(classement impossible"):
        raise ModeleInjoignable(resume)
    return Lu(entreprise, typ, plateforme, resume=resume)


def lire_avec_le_modele(m):
    """Mail d'un logiciel de recrutement ou d'une entreprise : le modèle dit s'il s'agit d'une candidature
    de l'étudiant, de quelle entreprise, quel poste et ce qu'il annonce. None si ce n'en est pas une."""
    try:
        reponse = modele.llm_json(
            "Voici un mail reçu par un étudiant qui cherche une alternance.\n"
            f"Expéditeur : {m['de']}\nSujet : {m['sujet']}\n---\n{_texte(m['corps'])[:3000]}\n---\n"
            "Ce mail parle-t-il d'une candidature que l'étudiant a envoyée (accusé de réception, réponse, refus, "
            "entretien…) ? Réponds en JSON : "
            '{"candidature": true | false, "entreprise": "entreprise ou cabinet qui recrute (pas le logiciel ni le '
            'site d\'emploi)", "poste": "intitulé du poste, vide si inconnu", '
            '"type": "automatique" | "entretien" | "disponibilites" | "positive" | "refus" | "transmise" | "autre", '
            '"resume": "une phrase"}. "automatique" = accusé de réception sans décision ; "transmise" = '
            "candidature transmise à un autre service ou aux RH, sans décision ; "
            '"disponibilites" = on demande ses disponibilités ou de convenir d\'un créneau (appel, entretien) '
            'sans date fixée ; "entretien" = entretien avec une date fixée. Ne devine pas l\'entreprise : '
            "vide si le mail ne la nomme pas.")
    except Exception as e:
        raise ModeleInjoignable(str(e)) from e
    if not reponse.get("candidature") or not str(reponse.get("entreprise") or "").strip():
        return None
    typ = reponse.get("type") if reponse.get("type") in ("automatique", "entretien", "disponibilites", "positive", "refus", "transmise") else "autre"
    return Lu(_propre(reponse["entreprise"]), typ, "Site de l'entreprise", str(reponse.get("poste") or "").strip(),
              resume=str(reponse.get("resume") or ""))
