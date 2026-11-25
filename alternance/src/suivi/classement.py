"""Classement d'une réponse reçue par le modèle, et réponses reconnues par leur contenu (signature surtout)."""
import re

from mails import DOMAINES_PERSO, domaine, est_adresse
from modele import llm_json
from rapprochement import preuves_dans_le_mail
from tableau import HORS_MAIL


def classer_reponse(entreprise, sujet, corps):
    try:
        r = llm_json(
            f"Un étudiant a candidaté pour une alternance chez « {entreprise} ». Voici une réponse reçue.\n"
            f"Sujet : {sujet}\n---\n{corps[:3000]}\n---\n"
            'Classe-la : {"type": "entretien" | "disponibilites" | "positive" | "refus" | "transmise" | "automatique" | "autre", '
            '"resume": "une phrase"}. "automatique" = accusé de réception automatique sans décision. '
            '"disponibilites" = on demande ses disponibilités ou de convenir d\'un créneau (appel, entretien) '
            'sans date fixée ; "entretien" = entretien avec une date fixée. '
            '"transmise" = la personne dit avoir transmis / transféré / fait suivre la candidature à un autre '
            'service, aux RH ou à un collègue, sans décision pour l\'instant.')
        return r.get("type", "autre"), r.get("resume", "")
    except Exception as e:
        return "autre", f"(classement impossible : {e})"


def reconnus_par_le_contenu(suivi, recus, ndr, statuts_actifs):
    """Mails reçus d'une adresse inconnue (perso, outil…) reconnus par leur contenu, la signature surtout :
    domaine, téléphone, ou nom + code postal / ville d'UNE SEULE candidature suivie. {id(mail): (ligne, preuves)}.
    Les mails venant du domaine d'une entreprise du tableau sont laissés aux règles d'adresse."""
    lignes = []
    for r in suivi.rows():
        statut = suivi.get(r, "Statut") or ""
        if (statut in statuts_actifs or statut in HORS_MAIL) and not statut.startswith("Brouillon"):
            site = re.search(r"Site : (\S+)", str(suivi.get(r, "Notes") or ""))
            lignes.append((r[0].row, suivi.get(r, "Entreprise"), str(suivi.get(r, "Email") or "").strip().lower(),
                           suivi.get(r, "Lieu"), suivi.get(r, "Téléphone"), site.group(1) if site else ""))
    # domaines de TOUTES les entreprises du tableau (une entreprise déjà refusée qui écrit ne compte pas pour une autre)
    domaines_tableau = {domaine(str(suivi.get(r, "Email") or "").strip().lower()) for r in suivi.rows()} \
        - set(DOMAINES_PERSO) - {""}
    from .ailleurs_lecture import nomme_l_entreprise   # (import ici : ailleurs_lecture importe ce module)
    res = {}
    for m in recus:
        if m in ndr or not est_adresse(m["de"]) or domaine(m["de"]) in domaines_tableau:
            continue
        if nomme_l_entreprise(m):                # l'objet nomme l'entreprise : lu par son format (ailleurs.py)
            continue
        corps = f"{m['sujet']}\n{m['corps']}"
        trouves = [(n, p) for n, ent, mail, lieu, tel, site in lignes
                   if (p := preuves_dans_le_mail(corps, ent, mail, lieu, tel, site))]
        if len(trouves) == 1:                    # plusieurs candidatures possibles : dans le doute, aucune
            res[id(m)] = trouves[0]
    return res
