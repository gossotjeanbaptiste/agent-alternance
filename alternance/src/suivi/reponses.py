"""Mails reçus pour une candidature : avis de non-remise (adresse invalide), réponses rattachées
(voir rapprochement.py) puis classées par le modèle."""
import re

from commun import CFG, say
from mails import DOMAINES_PERSO, domaine, est_adresse
from rapprochement import correspond
from tableau import DISPONIBILITES, TRANSMISE, norm
from . import classement

STATUT_DU_TYPE = {"entretien": "Entretien", "positive": "Réponse positive", "refus": "Refus", "transmise": TRANSMISE,
                  "disponibilites": DISPONIBILITES}


def adresse_invalide(p, l):
    """Avis de non-remise vers les adresses depuis l'envoi : statut « Adresse invalide » si TOUTES les adresses de la
    candidature sont revenues (vrai dans ce cas) ; si une partie seulement, l'adresse refusée est notée dans Notes
    (une fois) et le suivi continue avec les autres.
    (Candidature faite autrement qu'en mail : un avis vers son adresse ne la concerne pas.)"""
    mails = l.mails or ([l.mail] if l.mail else [])
    if not mails or l.hors_mail:
        return False
    avis = [(m["corps"] + m["sujet"]).lower() for m in p.ndr if m["date"].date() >= l.depuis]
    refusees = [a for a in mails if any(a in t for t in avis)]
    if not refusees:
        return False
    s = p.suivi
    notes = str(s.get(l.row, "Notes") or "")
    if len(refusees) < len(mails):
        nouvelles = [a for a in refusees if f"Adresse refusée : {a}" not in notes]
        if nouvelles:
            s.set(l.row, "Notes", (" ".join(f"Adresse refusée : {a}." for a in nouvelles) + " " + notes).strip())
            say(f"   ⚠️ {l.ent} : adresse {', '.join(nouvelles)} refusée (avis de non-remise) ; "
                f"suivi poursuivi avec {', '.join(a for a in mails if a not in refusees)}")
        return False
    s.set(l.row, "Statut", "Adresse invalide")
    s.set(l.row, "Notes", f"Avis de non-remise reçu. {notes}".strip())
    say(f"   ❌ {l.ent} : adresse {', '.join(mails)} invalide")
    p.bilan["adresse(s) invalide(s)"] += 1
    return True


def _rattachees(p, l):
    """Mails reçus depuis l'envoi qui concernent cette candidature : même adresse, même domaine s'il est propre à
    l'entreprise dans le tableau (ex. un domaine d'université sur 2 lignes -> adresse exacte uniquement), outil à
    son nom (…@entreprise.on.crisp.email), mot distinctif du nom dans l'adresse (prenom.entreprise@gmail.com),
    ou contenu (signature) qui ne désigne qu'elle."""
    def dom_ok(a):
        dom = domaine(a)
        return bool(dom) and dom not in DOMAINES_PERSO and dom not in CFG.get("domaines_ignores", [])             and p.nb_domaines[dom] == 1
    mails = [(a, dom_ok(a)) for a in (l.mails or [l.mail])]
    distinctifs = p.distinctifs.get(norm(l.ent), set())
    ligne = l.row[0].row
    reps = []
    for m in p.recus:
        if m["date"].date() < l.depuis or not est_adresse(m["de"]) or m in p.ndr:
            continue
        par_adresse = any(correspond(m["de"], a, ok, distinctifs) for a, ok in mails)
        par_contenu = p.par_contenu.get(id(m), (None,))[0] == ligne
        if par_contenu and not par_adresse:
            say(f"   🔎 {l.ent} : mail de {m['de']} reconnu grâce à son contenu ({', '.join(p.par_contenu[id(m)][1])})")
        if par_adresse or par_contenu:
            reps.append(m)
            p.rattaches.add(id(m))
    return reps


def reponses_recues(p, l):
    """Classe les nouvelles réponses et met le statut à jour. Vrai si une vraie réponse est arrivée (fin du suivi)."""
    s = p.suivi
    reps = _rattachees(p, l)
    traitees = "" if l.a_reclasser else str(s.get(l.row, "Dernière réponse") or "")
    # seulement les mails plus récents que la dernière réponse traitée (« Dernière réponse » commence
    # par sa date) : sinon, après une 2e réponse, la 1re serait reclassée à chaque passage
    derniere_traitee = traitees[:16] if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", traitees) else ""
    reps = [m for m in reps if f"{m['date']:%Y-%m-%d %H:%M}" > derniere_traitee]
    repondu = False
    for m in sorted(reps, key=lambda x: x["date"]):
        typ, resume = classement.classer_reponse(l.ent, m["sujet"], m["corps"])
        s.set(l.row, "Dernière réponse", f"{m['date']:%Y-%m-%d %H:%M} [{typ}] {resume}")
        if typ != "automatique":
            s.set(l.row, "Statut", STATUT_DU_TYPE.get(typ, "Réponse à lire"))
            s.set(l.row, "Relance prévue", None)
            repondu = True
        say(f"   📩 {l.ent} : réponse [{typ}] {resume}")
        p.bilan["accusé(s) de réception automatique(s)" if typ == "automatique" else "réponse(s) classée(s)"] += 1
    return repondu
