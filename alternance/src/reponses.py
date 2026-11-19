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

SPONTANEE = "Candidature spontanée"   # poste noté quand La Bonne Alternance n'a pas d'offre pour l'entreprise

# Le modèle inventait le secteur d'une entreprise d'après son nom (« Xxx Tech » -> « éditeur de logiciels de… ») :
# règle ajoutée à toutes les consignes de lettre et de réponses.
NE_PAS_INVENTER = (
    "RÈGLE ABSOLUE SUR L'ENTREPRISE : son secteur d'activité, ses produits, ses services, ses clients, ses projets ou "
    "ses technologies ne peuvent venir QUE de « Ce qu'on sait de l'entreprise » ci-dessus, recopiés sans rien ajouter. "
    "Ne déduis RIEN de son nom ni de sa ville, ne devine pas son métier. Si cette information manque (« rien de plus »), "
    "ne nomme aucun secteur, produit ou client : parle de l'entreprise en termes généraux (son équipe, l'intérêt du "
    "poste, ce que l'alternance m'apportera et ce que je peux apporter). Ne commente JAMAIS le nom de l'entreprise : "
    "ne dis pas qu'il m'inspire, m'évoque, m'attire, me parle ou reflète quelque chose.\n")


def infos_du_tableau(notes):
    """Ce que le tableau sait vraiment de l'entreprise (colonne Notes) : activité officielle et site, pour le modèle."""
    import re
    morceaux = [m.strip() for m in str(notes or "").split("|")]
    return " | ".join(m for m in morceaux if re.match(r"(Activité|Site) : \S", m))


def questions_attendues(statut, poste=None):
    """Vrai si le formulaire pose les trois questions : toute candidature par le formulaire La Bonne Alternance,
    offre ou candidature spontanée (le site les demande dans les deux cas). Formulaire du site : la lettre seule."""
    from tableau import LBA
    return statut == LBA


def manque(statut, lien, lettre_connue, deja):
    """[« la lettre », « les réponses »] : ce qu'il reste à écrire pour une candidature par formulaire
    (bouton « Écrire ce qui manque » et routine « Réponses La Bonne Alternance »)."""
    a_faire = [] if lettre_connue else ["la lettre"]
    if questions_attendues(statut) and not a_des_reponses(deja.get(lien)):
        a_faire.append("les réponses")
    return a_faire


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
        "sans formule de politesse, sans inventer d'expérience absente du profil.\n"
        + NE_PAS_INVENTER + interdits() +
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
    # écrit à côté puis remplace d'un seul coup : un arrêt en pleine écriture ne laisse pas un fichier coupé
    provisoire = FICHIER.with_name(FICHIER.name + ".enregistrement")
    provisoire.write_text(json.dumps(tout, ensure_ascii=False, indent=1), encoding="utf-8")
    import os
    os.replace(provisoire, FICHIER)


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
