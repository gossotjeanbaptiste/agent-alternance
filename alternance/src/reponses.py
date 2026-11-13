"""Candidatures par formulaire (La Bonne Alternance, site de l'entreprise) : lettre et réponses.

Pas de brouillon dans la messagerie pour ces candidatures : la lettre et les réponses aux
questions du formulaire La Bonne Alternance sont gardées dans alternance/donnees/reponses_lba.json
(données personnelles, non versionné), rangées par lien pour postuler.
"""
import json

import commun
import donnees
import reglages
from commun import PROFIL, interdits

FICHIER = donnees.chemin("reponses_lba.json")

# (clé, titre affiché, consigne pour le modèle) : modifiables dans la page Paramètres
QUESTIONS = [(cle, reglages.valeur(f"redaction.questions.{cle}.titre"),
              reglages.valeur(f"redaction.questions.{cle}.consigne")) for cle in reglages.QUESTIONS]

def rediger_reponses(o):
    """{clé: texte} des réponses pour l'entreprise o (entreprise, poste, lieu, infos)."""
    from modele import llm_json
    consignes = "\n".join(f'- "{cle}" : {consigne}' for cle, _, consigne in QUESTIONS)
    r = llm_json(
        f"{PROFIL}\n\n---\nJe postule via un formulaire en ligne qui pose trois questions. "
        f"Rédige mes réponses, à la première personne, pour cette entreprise :\n"
        f"- Entreprise : {o['entreprise']}\n- Poste / offre : {o.get('poste') or 'candidature spontanée'}\n"
        f"- Lieu : {o.get('lieu') or '?'}\n- Ce qu'on sait de l'entreprise : {o.get('infos') or 'rien de plus'}\n\n"
        f"Questions :\n{consignes}\n\n"
        f"Chaque réponse : {reglages.valeur('redaction.longueur_reponses')}, ton sincère et professionnel, "
        "sans formule de politesse, sans inventer d'expérience absente du profil. "
        "Si on ne sait rien de l'entreprise, appuie-toi sur son nom et son secteur sans inventer de faits.\n"
        + interdits() +
        "{" + ", ".join(f'"{cle}": "..."' for cle, _, _ in QUESTIONS) + "}")
    return {cle: str(r.get(cle) or "").strip() for cle, _, _ in QUESTIONS}


def lire():
    try:
        return json.loads(FICHIER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def enregistrer(lien, reponses):
    """Ajoute (ou remplace) des champs pour ce lien : réponses aux questions et/ou "lettre"."""
    if commun.ESSAI or not lien:
        return
    tout = lire()
    tout.setdefault(lien, {}).update(reponses)
    FICHIER.write_text(json.dumps(tout, ensure_ascii=False, indent=1), encoding="utf-8")


def enregistrer_lettre(lien, lettre):
    enregistrer(lien, {"lettre": lettre})


def lettres():
    """{lien: lettre} des candidatures par formulaire."""
    return {lien: d["lettre"] for lien, d in lire().items() if d.get("lettre")}


def a_des_reponses(d):
    return bool(d) and any(d.get(cle) for cle, _, _ in QUESTIONS)


def en_liste(reponses):
    """[(titre, texte)] dans l'ordre du formulaire (pour l'affichage)."""
    return [(titre, reponses.get(cle, "")) for cle, titre, _ in QUESTIONS if reponses.get(cle)]
