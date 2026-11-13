"""Candidatures par formulaire (La Bonne Alternance, site de l'entreprise) : lettre et réponses.

Pas de brouillon dans la messagerie pour ces candidatures : la lettre et les réponses aux
questions du formulaire La Bonne Alternance sont gardées dans alternance/reponses_lba.json
(données personnelles, non versionné), rangées par lien pour postuler.
"""
import json

import commun
from commun import HERE, PROFIL

FICHIER = HERE / "reponses_lba.json"

# (clé, titre affiché, consigne pour le modèle)
QUESTIONS = [
    ("motivations", "Vos motivations : pourquoi souhaitez-vous rejoindre l'entreprise ?",
     "pourquoi je souhaite rejoindre cette entreprise précisément (son activité, ce qui m'attire chez elle)"),
    ("missions", "Quelles missions souhaiteriez-vous accomplir au sein de l'entreprise ?",
     "le poste visé, les missions que je souhaite accomplir et ma contribution concrète aux activités de l'entreprise"),
    ("experiences", "Vos expériences passées (stage, job, bénévolat) en lien avec le poste visé",
     "mes expériences passées (stages, jobs, bénévolat, projets) en lien avec le poste visé, et ce qu'elles m'ont apporté"),
]


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
        "Chaque réponse : 4 à 6 phrases (environ 600 à 900 caractères), ton sincère et professionnel, "
        "sans formule de politesse, sans inventer d'expérience absente du profil. "
        "Si on ne sait rien de l'entreprise, appuie-toi sur son nom et son secteur sans inventer de faits.\n"
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
