"""Consignes du modèle pour les deux rapports de la page Rapport :
- « moi » : point d'étape pour l'étudiant (ce qui marche, ce qui bloque, conseils) ;
- « ecole » : rapport formel à remettre à l'école (démarches, résultats, suite), écrit à la première personne,
  suivi d'une annexe « Entreprises contactées » construite par le code (jamais par le modèle : rien d'inventé).
"""

TYPES = {"moi": "pour moi", "ecole": "pour l'école"}

_REGLES = """Règles :
- reprends les chiffres EXACTS ; ne confonds pas les chiffres de la période avec ceux de tout le tableau ;
- n'invente aucune entreprise, aucun chiffre, aucune réponse, aucun entretien ;
- si une information manque, dis-le simplement ; pas de tableau Markdown, des listes à puces au besoin."""


def _structure(titres):
    return ("Structure : un titre « # Rapport de recherche d'alternance » suivi des dates, puis exactement ces parties, "
            "avec ces titres mot pour mot et rien d'autre sur la ligne du titre :\n"
            + "\n".join(f"## {t}" for t in titres))


MOI = {
    "systeme": ("Tu es un conseiller qui aide un étudiant à faire le point sur sa recherche d'alternance. "
                "Tu écris en français, de façon claire, concrète et bienveillante, sans flatterie."),
    "titres": ["Synthèse", "Activité", "Réponses et retours", "Ce qui fonctionne, ce qui bloque", "Prochaines étapes",
               "Conseils"],
    "contenu": """Contenu attendu (consignes pour toi, à ne JAMAIS recopier dans le rapport) :
- Synthèse : un court paragraphe sur où en est la recherche.
- Activité : candidatures envoyées pendant la période, canaux, sources, travail des routines automatiques.
- Réponses et retours : réponses reçues et ce qu'elles disent (refus, demandes de disponibilités, entretiens…), taux.
- Ce qui fonctionne, ce qui bloque : d'après les chiffres et les réponses.
- Prochaines étapes : relances prévues, candidatures à finaliser, réponses à donner, avec les noms d'entreprises.
- Conseils : quelques conseils concrets adaptés à ces données et au profil.""",
}

ECOLE = {
    "systeme": ("Tu aides un étudiant à rédiger le rapport de sa recherche d'alternance destiné à son école "
                "(responsable de formation, chargé des relations entreprises). Tu écris en français, à la première "
                "personne (« j'ai contacté… »), dans un registre professionnel, sobre et factuel."),
    "titres": ["Synthèse", "Démarches réalisées", "Résultats obtenus", "Analyse", "Suite de ma recherche"],
    "contenu": """Contenu attendu (consignes pour toi, à ne JAMAIS recopier dans le rapport) :
- Synthèse : en quelques phrases, le poste recherché, la période et l'état de la recherche.
- Démarches réalisées : nombre de candidatures, canaux utilisés (mail, La Bonne Alternance, formulaires, LinkedIn…),
  sources des entreprises, relances effectuées. Ne parle pas des outils ni de l'automatisation.
- Résultats obtenus : réponses reçues, entretiens, refus, taux de réponse, candidatures encore en attente.
- Analyse : ce que montrent ces résultats, sans te dévaloriser ni exagérer.
- Suite de ma recherche : ce que je vais faire dans les prochaines semaines (relances, nouvelles candidatures…).
Pas de conseils, pas de liste d'entreprises : la liste détaillée est ajoutée en annexe automatiquement.""",
}


def consignes(type_):
    c = ECOLE if type_ == "ecole" else MOI
    return c["systeme"], f"""Rédige le rapport de recherche d'alternance de l'étudiant pour la période indiquée, en Markdown,
à partir UNIQUEMENT des données ci-dessous.

{_structure(c["titres"])}

{c["contenu"]}

{_REGLES}"""


def annexe(envoyees):
    """Annexe du rapport pour l'école : les candidatures envoyées de la période, d'après le tableau (Markdown)."""
    if not envoyees:
        return "## Annexe : entreprises contactées\n\nAucune candidature envoyée sur la période."
    lignes = ["## Annexe : entreprises contactées", "",
              f"{len(envoyees)} candidature(s) envoyée(s) sur la période (date d'envoi, entreprise, poste, lieu, "
              "suite donnée) :", ""]
    for l in sorted(envoyees, key=lambda x: x["Date envoi"]):
        morceaux = [f"{l['Date envoi']:%d/%m/%Y}", f"**{l.get('Entreprise') or '?'}**"]
        morceaux += [str(l[c]) for c in ("Poste", "Lieu") if l.get(c)]
        morceaux.append(str(l.get("Statut") or ""))
        lignes.append("- " + " — ".join(m for m in morceaux if m))
    return "\n".join(lignes)
