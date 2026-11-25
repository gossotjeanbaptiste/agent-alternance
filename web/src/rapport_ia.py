"""Rapport rédigé par le modèle local (la tour, sinon ce PC) à partir du bilan de la page Rapport.

Rédigé en arrière-plan (la page suit l'avancement par /api/rapport/etat), enregistré dans le dossier
personnel « rapports » (rapport_AAAA-MM-JJ_HHMM.md), puis le modèle est déchargé.
"""
import re
import threading
from datetime import datetime

import emplacements
import rapport_contexte
import routines

ETAT = {"etat": "inactif", "message": "", "fichier": ""}   # inactif | en cours | fini | erreur
SYSTEME = ("Tu es un conseiller qui aide un étudiant à faire le point sur sa recherche d'alternance. "
           "Tu écris en français, de façon claire, concrète et bienveillante, sans flatterie.")
TITRES = ["Synthèse", "Activité", "Réponses et retours", "Ce qui fonctionne, ce qui bloque", "Prochaines étapes",
          "Conseils"]
CONSIGNES = """Rédige le rapport de recherche d'alternance de l'étudiant pour la période indiquée, en Markdown,
à partir UNIQUEMENT des données ci-dessous.

Structure : un titre « # Rapport de recherche d'alternance » suivi des dates, puis exactement ces parties,
avec ces titres mot pour mot et rien d'autre sur la ligne du titre :
""" + "\n".join(f"## {t}" for t in TITRES) + """

Contenu attendu (consignes pour toi, à ne JAMAIS recopier dans le rapport) :
- Synthèse : un court paragraphe sur où en est la recherche.
- Activité : candidatures envoyées pendant la période, canaux, sources, travail des routines automatiques.
- Réponses et retours : réponses reçues et ce qu'elles disent (refus, demandes de disponibilités, entretiens…), taux.
- Ce qui fonctionne, ce qui bloque : d'après les chiffres et les réponses.
- Prochaines étapes : relances prévues, candidatures à finaliser, réponses à donner, avec les noms d'entreprises.
- Conseils : quelques conseils concrets adaptés à ces données et au profil.

Règles :
- reprends les chiffres EXACTS ; ne confonds pas les chiffres de la période avec ceux de tout le tableau ;
- n'invente aucune entreprise, aucun chiffre, aucune réponse, aucun entretien ;
- si une information manque, dis-le simplement ; pas de tableau Markdown, des listes à puces au besoin."""


def dossier():
    d = emplacements.dossier("rapports")
    d.mkdir(parents=True, exist_ok=True)
    return d


def enregistres(n=20):
    """Noms des rapports déjà rédigés, du plus récent au plus ancien."""
    return [f.name for f in sorted(dossier().glob("rapport_*.md"), reverse=True)[:n]]


def lire(nom):
    """Texte d'un rapport enregistré (nom vérifié : rien en dehors du dossier), ou ""."""
    if not nom:
        return ""
    f = (dossier() / nom).resolve()
    if f.parent != dossier().resolve() or not f.name.startswith("rapport_") or f.suffix != ".md" or not f.is_file():
        return ""
    return nettoyer(f.read_text(encoding="utf-8", errors="replace"))   # rapports d'avant aussi


def nettoyer(texte):
    """Titres de parties sans la consigne recopiée par le modèle (« ## Synthèse — 4 à 6 phrases : … » -> « ## Synthèse ») :
    coupés au premier tiret long ; le titre principal (« # … », avec les dates) est gardé tel quel."""
    return re.sub(r"^(#{2,4}\s.*?)\s+[—–]\s.*$", r"\1", (texte or "").strip(), flags=re.M)


def rediger(r):
    """Fait écrire le rapport au modèle (bloquant). Renvoie le nom du fichier enregistré."""
    import agent
    import chemins  # noqa: F401
    import modele
    agent.ensure_server()
    texte = nettoyer(modele.llm(CONSIGNES + "\n\n=== DONNÉES ===\n" + rapport_contexte.contexte(r),
                                system=SYSTEME, temperature=0.4))
    if not texte:
        raise RuntimeError("le modèle n'a rien écrit")
    nom = f"rapport_{datetime.now():%Y-%m-%d_%H%M}.md"
    (dossier() / nom).write_text(texte + "\n", encoding="utf-8")
    agent.log(f"📄 Rapport rédigé par le modèle ({r['debut']:%d/%m/%Y} → {r['fin']:%d/%m/%Y}) : {nom}")
    return nom


def _travail(r):
    import redaction
    try:
        ETAT.update(etat="fini", fichier=rediger(r), message="Rapport rédigé.")
    except SystemExit:                       # serveur du modèle injoignable (agent.ensure_server)
        ETAT.update(etat="erreur", message="Le modèle ne répond pas : vérifie LM Studio (sur la tour ou ce PC).")
    except Exception as e:
        ETAT.update(etat="erreur", message=f"Rédaction impossible : {e}")
    finally:
        try:
            import agent
            agent.liberer_modele()           # sinon le modèle resterait chargé tant que l'interface tourne
        except Exception:
            pass
        redaction.VERROU.release()


def lancer(args, lignes=None):
    """Lance la rédaction en arrière-plan pour la période demandée. Renvoie (ok, message)."""
    import rapport
    import redaction
    if routines.en_cours():
        return False, "Une routine est en cours (elle utilise le modèle) : attends qu'elle se termine."
    if not redaction.VERROU.acquire(blocking=False):
        return False, "Le modèle est déjà en train d'écrire : attends qu'il ait fini."
    try:
        r = rapport.generer(args, lignes)
    except Exception as e:
        redaction.VERROU.release()
        return False, f"Lecture du tableau impossible : {e}"
    ETAT.update(etat="en cours", fichier="", message="Le modèle rédige le rapport (réveil de la tour et chargement compris, "
                "compte quelques minutes)…")
    threading.Thread(target=_travail, args=(r,), daemon=True).start()
    return True, ETAT["message"]
