"""Candidatures faites en dehors de LM Agent (Indeed, HelloWork, LinkedIn, La Bonne Alternance, site d'une
entreprise…) : leurs accusés de réception et réponses, reçus par mail, complètent le tableau.

Après la revue des candidatures du tableau, chaque mail reçu qu'aucune ligne n'a rattaché et qui parle d'une
candidature est lu (ailleurs_lecture.py), puis :
- entreprise déjà dans le tableau : « À postuler » -> « Candidaté (…) » à la date du mail, réponse classée ;
- sinon nouvelle ligne, si le poste est de l'informatique (pas « Serveur H/F » d'une candidature à côté).
Les mails lus sont notés dans donnees/mails_candidatures.json : ils ne sont pas relus (ni rajoutés si tu
supprimes la ligne). Un mail que le modèle n'a pas pu lire est relu au passage suivant.
"""
import difflib
import json
import re
import unicodedata

import commun
import donnees
import reglages
from commun import CFG, say
from mails import DOMAINES_PERSO, domaine
from mails import adresses as adresses_cellule
from tableau import A_POSTULER, C_AUTRE, C_FORMULAIRE, C_LBA, C_LINKEDIN, FORMULAIRE, LBA, as_date, norm
from .ailleurs_lecture import ModeleInjoignable, lire_avec_le_modele, lire_format_connu
from .reponses import STATUT_DU_TYPE

FICHIER = "mails_candidatures.json"
GARDES = 3000          # mails lus dont on garde la trace
MAX_MODELE = 40        # mails confiés au modèle par passage (les suivants au passage d'après)
FINAUX = {"Accepté", "Abandonné"}
CANAL = {"La Bonne Alternance": C_LBA, "LinkedIn": C_LINKEDIN, "Site de l'entreprise": C_FORMULAIRE}


def _cle(m):
    return f"{m['date']:%Y-%m-%d %H:%M}|{m['de'].lower()}|{m['sujet'].strip()}"


def _deja_lus():
    try:
        return json.loads(donnees.chemin(FICHIER).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def _noter_lus(lus):
    if not commun.ESSAI:
        donnees.chemin(FICHIER).write_text(json.dumps(lus[-GARDES:], ensure_ascii=False, indent=1), encoding="utf-8")


def _sans_accents(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def informatique(poste):
    """Poste inconnu (candidature spontanée…) ou qui contient l'un des mots d'un poste en informatique."""
    if not poste or _sans_accents(poste).startswith("candidature spontan"):
        return True
    p = _sans_accents(poste)
    for mot in reglages.valeur("suivi_ailleurs.mots_postes"):
        mot = _sans_accents(mot).strip()
        # mots courts (« it », « ia », « web ») : mot entier seulement (pas le « it » de « recruteur ditto »)
        if mot and (re.search(rf"(?<![a-z0-9]){re.escape(mot)}(?![a-z0-9])", p) if len(mot) <= 3 else mot in p):
            return True
    return False


def _meme_nom(a, b):
    return bool(b) and (a == b or (min(len(a), len(b)) >= 5 and (a in b or b in a)))


def _ligne(suivi, lu, jour):
    """Ligne du tableau de cette candidature, ou None (entreprise absente, ou même entreprise pour un autre poste)."""
    n = norm(lu.entreprise)
    memes = [r for r in suivi.rows() if _meme_nom(n, norm(suivi.get(r, "Entreprise")))] if len(n) >= 2 else []
    if not memes or not lu.poste:
        return memes[-1] if memes else None
    for r in reversed(memes):
        poste, statut = str(suivi.get(r, "Poste") or ""), suivi.get(r, "Statut") or ""
        envoi = as_date(suivi.get(r, "Date envoi"))
        if not poste or _sans_accents(poste).startswith("candidature spontan") or statut in A_POSTULER \
                or statut.startswith("Brouillon") or (envoi and abs((jour - envoi).days) <= 2) \
                or difflib.SequenceMatcher(None, norm(poste), norm(lu.poste)).ratio() >= 0.6:
            return r
    return None


def _date_traitee(texte):
    return texte[:16] if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", texte) else ""


def _derniere_reponse(m, lu):
    quoi = lu.resume or f"accusé de réception ({lu.plateforme})"
    return f"{m['date']:%Y-%m-%d %H:%M} [{lu.type}] {quoi}"


def _canal(lu, statut):
    if statut == LBA:
        return C_LBA
    if statut == FORMULAIRE:
        return C_FORMULAIRE
    return CANAL.get(lu.plateforme, C_AUTRE)


def _mettre_a_jour(p, row, m, lu):
    s = p.suivi
    ent, statut, jour = s.get(row, "Entreprise"), s.get(row, "Statut") or "", m["date"].date()
    # mail déjà connu de cette ligne (« Dernière réponse » plus récente ou égale) : rien de nouveau
    if statut in FINAUX or f"{m['date']:%Y-%m-%d %H:%M}" <= _date_traitee(str(s.get(row, "Dernière réponse") or "")):
        return
    if lu.type == "echec":
        if statut not in (LBA, C_LBA):
            return
        s.set(row, "Statut", "Adresse invalide")
        s.set(row, "Notes", f"{lu.resume}. {s.get(row, 'Notes') or ''}".strip())
        say(f"   ❌ {ent} : {lu.resume}")
        p.bilan["adresse(s) invalide(s)"] += 1
    elif lu.type == "automatique":
        if statut in A_POSTULER or statut.startswith("Brouillon") or not statut:
            s.set(row, "Statut", _canal(lu, statut))
            s.set(row, "Date envoi", jour)
            s.set(row, "Dernière action", jour)
            s.set(row, "Relance prévue", None)
            say(f"   ✅ {ent} : candidature ({lu.plateforme}) confirmée le {jour:%d/%m}")
            p.bilan["candidature(s) faite(s) ailleurs confirmée(s)"] += 1
        else:
            p.bilan["accusé(s) de réception automatique(s)"] += 1
    else:
        s.set(row, "Statut", STATUT_DU_TYPE.get(lu.type, "Réponse à lire"))
        s.set(row, "Relance prévue", None)
        say(f"   📩 {ent} : réponse [{lu.type}] {lu.resume} (via {lu.plateforme})")
        p.bilan["réponse(s) classée(s)"] += 1
    s.set(row, "Dernière réponse", _derniere_reponse(m, lu))


def _ajouter(p, m, lu):
    if lu.type == "echec":
        return                                    # candidature pas partie : rien à suivre
    if not informatique(lu.poste):
        say(f"   ⏭️  {lu.entreprise} ({lu.plateforme}) : « {lu.poste} » n'est pas un poste en informatique, pas ajouté")
        return
    jour = m["date"].date()
    statut = CANAL.get(lu.plateforme, C_AUTRE) if lu.type == "automatique" else STATUT_DU_TYPE.get(lu.type, "Réponse à lire")
    p.suivi.add(**{"Date ajout": jour, "Entreprise": lu.entreprise, "Poste": lu.poste, "Lieu": lu.lieu,
                   "Source": lu.plateforme, "Statut": statut, "Date envoi": jour, "Dernière action": jour,
                   "Dernière réponse": _derniere_reponse(m, lu),
                   "Notes": f"Ajoutée d'après le mail « {m['sujet'].strip()} » du {jour:%d/%m/%Y} "
                            "(candidature faite en dehors de LM Agent)."})
    say(f"   ➕ {lu.entreprise}{f' — {lu.poste}' if lu.poste else ''} ({lu.plateforme}) : ajoutée au tableau, « {statut} »")
    p.bilan["candidature(s) faite(s) ailleurs ajoutée(s)"] += 1


def traiter(p):
    """Mails reçus non rattachés à une ligne : accusés de réception et réponses de candidatures faites ailleurs."""
    if not reglages.valeur("suivi_ailleurs.actif"):
        return
    lus = _deja_lus()
    deja, au_modele, en_attente = set(lus), 0, 0
    # adresses et domaines des entreprises du tableau : leurs mails relèvent du rattachement habituel (reponses.py),
    # même quand il les écarte (mail d'avant l'envoi, domaine partagé…) ; domaines de l'école : jamais
    adresses = {a for r in p.suivi.rows() for a in adresses_cellule(p.suivi.get(r, "Email"))}
    ignores = ({domaine(a) for a in adresses} - set(DOMAINES_PERSO)) | set(CFG.get("domaines_ignores", []))
    for m in sorted(p.recus, key=lambda x: x["date"]):
        if id(m) in p.rattaches or not m["de"] or m in p.ndr or _cle(m) in deja \
                or m["de"].lower() in adresses or domaine(m["de"]) in ignores:
            continue
        try:
            lu = lire_format_connu(m)
            if lu is None:
                continue                          # rien à voir (lecture sans le modèle : pas besoin de le noter)
            if lu is ...:
                if au_modele >= MAX_MODELE:
                    en_attente += 1
                    continue
                au_modele += 1
                lu = lire_avec_le_modele(m)
        except ModeleInjoignable:
            en_attente += 1
            continue
        deja.add(_cle(m))
        lus.append(_cle(m))
        if lu is None:
            continue
        row = _ligne(p.suivi, lu, m["date"].date())
        if row is None:
            _ajouter(p, m, lu)
        else:
            _mettre_a_jour(p, row, m, lu)
    _noter_lus(lus)
    if en_attente:
        say(f"   ⏳ {en_attente} mail(s) de candidature pas encore lu(s) (modèle injoignable, ou plus de {MAX_MODELE} "
            "à lire) : ils le seront au prochain passage")
