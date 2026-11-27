"""Rapport rédigé par le modèle local (la tour, sinon ce PC) à partir du bilan de la page Rapport :
« pour moi » ou « pour l'école » (consignes dans rapport_consignes.py ; annexe de l'école écrite par le code).

Rédigé en arrière-plan (la page suit l'avancement par /api/rapport/etat), enregistré dans le dossier
personnel « rapports » (rapport_AAAA-MM-JJ_HHMM.md, ou …_ecole.md), puis le modèle est déchargé.
"""
import re
import threading
from datetime import datetime

import emplacements
import rapport_consignes
import rapport_contexte
import routines

ETAT = {"etat": "inactif", "message": "", "fichier": ""}   # inactif | en cours | fini | erreur
NOM = re.compile(r"^rapport_(\d{4})-(\d\d)-(\d\d)_(\d\d)(\d\d)(?:_(ecole))?\.md$")


def dossier():
    d = emplacements.dossier("rapports")
    d.mkdir(parents=True, exist_ok=True)
    return d


def enregistres(n=20):
    """Noms des rapports déjà rédigés, du plus récent au plus ancien."""
    return [d["nom"] for d in liste(n)]


def decrire(nom):
    """{nom, type ("moi" / "ecole"), libelle} d'un rapport enregistré d'après son nom, ou None."""
    m = NOM.match(nom)
    if not m:
        return None
    a, mo, j, h, mi, ecole = m.groups()
    type_ = "ecole" if ecole else "moi"
    return {"nom": nom, "type": type_, "quand": f"{a}{mo}{j}{h}{mi}",
            "libelle": f"Rapport {rapport_consignes.TYPES[type_]} du {j}/{mo}/{a} à {h}h{mi}"}


def liste(n=20):
    """Rapports enregistrés (decrire), du plus récent au plus ancien."""
    tout = [d for f in dossier().glob("rapport_*.md") if (d := decrire(f.name))]
    return sorted(tout, key=lambda d: d["quand"], reverse=True)[:n]


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


def rediger(r, type_="moi"):
    """Fait écrire le rapport au modèle (bloquant). Renvoie le nom du fichier enregistré."""
    import agent
    import chemins  # noqa: F401
    import modele
    agent.ensure_server()
    systeme, consignes = rapport_consignes.consignes(type_)
    texte = nettoyer(modele.llm(consignes + "\n\n=== DONNÉES ===\n" + rapport_contexte.contexte(r, ecole=type_ == "ecole"),
                                system=systeme, temperature=0.4))
    if not texte:
        raise RuntimeError("le modèle n'a rien écrit")
    if type_ == "ecole":       # liste des entreprises contactées : d'après le tableau, jamais d'après le modèle
        texte += "\n\n" + rapport_consignes.annexe(r["t"]["liste_envoyees"])
    nom = f"rapport_{datetime.now():%Y-%m-%d_%H%M}{'_ecole' if type_ == 'ecole' else ''}.md"
    (dossier() / nom).write_text(texte + "\n", encoding="utf-8")
    agent.log(f"📄 Rapport {rapport_consignes.TYPES[type_]} rédigé par le modèle "
              f"({r['debut']:%d/%m/%Y} → {r['fin']:%d/%m/%Y}) : {nom}")
    return nom


def _travail(r, type_="moi"):
    import redaction
    try:
        ETAT.update(etat="fini", fichier=rediger(r, type_), message="Rapport rédigé.")
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


def lancer(args, lignes=None, type_="moi"):
    """Lance la rédaction en arrière-plan pour la période demandée ; type_ : "moi" ou "ecole". Renvoie (ok, message)."""
    if type_ not in rapport_consignes.TYPES:
        return False, "Type de rapport inconnu."
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
    ETAT.update(etat="en cours", fichier="", message=f"Le modèle rédige le rapport {rapport_consignes.TYPES[type_]} "
                "(réveil de la tour et chargement compris, compte quelques minutes)…")
    threading.Thread(target=_travail, args=(r, type_), daemon=True).start()
    return True, ETAT["message"]
