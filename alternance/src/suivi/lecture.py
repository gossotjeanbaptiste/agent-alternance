"""mettre_a_jour : lit la messagerie, passe chaque candidature suivie en revue (envois, non-remises, réponses,
relances dues), affiche le bilan puis écrit les brouillons de relance dus."""
import re
from collections import Counter
from datetime import date, datetime

import commun
from commun import CFG, say
from jours import date_relance, prochain_ouvrable
from mails import domaine, est_adresse
from messagerie import nom_messagerie
from rapprochement import mots_distinctifs
from tableau import HORS_MAIL, MAIL, TRANSMISE, as_date
from . import ailleurs, envois, reponses
from .classement import reconnus_par_le_contenu
from .relance import preparer_relance

# « Candidature transmise » reste suivie (la réponse des RH sera classée) mais n'est plus relancée
STATUTS_ACTIFS = {"Brouillon", MAIL, "Relance en brouillon", "Relance programmée", "Relancé", TRANSMISE}
NON_REMIS = (r"non remis|undeliverable|delivery has failed|échec de la remise|"
             r"n'a pas pu être remis|could not be delivered")


class Passage:
    """Ce qu'une lecture de la messagerie a rassemblé, et ce qu'elle a changé (bilan, relances dues)."""
    def __init__(self, suivi, ol):
        self.suivi, self.ol = suivi, ol
        self.jours = self._jours()
        n = self._jours_depuis(self.jours)
        self.envois = ol.envois(n)
        self.recus = ol.recus(n)
        self._envois_complets = None if commun.DEPUIS else self.envois
        self.brouillons = ol.destinataires_brouillons()
        self.programmes = ol.programmes()
        if commun.GARDE:  # Outlook a répondu : la suite (le modèle) peut prendre le temps qu'il faut
            commun.GARDE.cancel()
        self.ndr = [m for m in self.recus if "REPORT" in m["classe"].upper() or re.search(NON_REMIS, m["sujet"], re.I)]
        self.aujourd_hui = date.today()
        self.a_relancer = []
        self.bilan = Counter()   # ce que ce passage a changé, résumé à la fin
        self.nb_domaines = Counter(domaine(str(suivi.get(r, "Email") or "").strip()) for r in suivi.rows())
        # mots du nom propres à une seule entreprise du tableau (réponse depuis une adresse personnelle)
        self.distinctifs = mots_distinctifs([suivi.get(r, "Entreprise") for r in suivi.rows()])
        self.par_contenu = reconnus_par_le_contenu(suivi, self.recus, self.ndr, STATUTS_ACTIFS)
        self.rattaches = set()   # id des mails rattachés à une ligne (les autres : candidatures faites ailleurs ?)

    @staticmethod
    def _jours_depuis(jours):
        """Mails envoyés et reçus : depuis la date choisie au lancement (--depuis, ex. le lundi de la semaine),
        sinon toute la période suivie (voir _jours)."""
        if not commun.DEPUIS:
            return jours
        say(f"   Mails envoyés et reçus lus depuis le {commun.DEPUIS:%d/%m/%Y}")
        return max(1, (date.today() - commun.DEPUIS).days + 1)

    def envois_complets(self):
        """Envois de toute la période suivie, lus seulement si une relance due a son mail d'origine avant la date
        choisie (il faut ce mail pour le transférer sous la relance)."""
        if self._envois_complets is None:
            say("   Relance due d'une candidature plus ancienne : lecture des mails envoyés plus anciens...")
            self._envois_complets = self.ol.envois(self.jours)
        return self._envois_complets

    def _jours(self):
        """On ne remonte pas plus loin que la plus ancienne candidature encore en cours (15 à 120 jours)."""
        s = self.suivi
        actives = [as_date(s.get(r, "Date envoi")) or as_date(s.get(r, "Date ajout")) for r in s.rows()
                   if (s.get(r, "Statut") or "").startswith(("Brouillon", "Candidaté", "Relance"))]
        actives = [d for d in actives if d]
        return min(120, max(15, (date.today() - min(actives)).days + 3)) if actives else 15


class Ligne:
    """Une candidature du tableau pendant la lecture ; statut et dernière action suivent ce qui est constaté."""
    def __init__(self, suivi, row):
        self.row = row
        self.ent = suivi.get(row, "Entreprise")
        self.mail = (suivi.get(row, "Email") or "").strip().lower()
        self.statut = suivi.get(row, "Statut") or ""
        if self.statut.startswith("Brouillon") and self.mail:  # adresse ajoutée à la main depuis
            self.statut = "Brouillon"
        # réponse qui n'a pas pu être classée (modèle injoignable) : on retente à ce passage
        self.a_reclasser = self.statut == "Réponse à lire" and \
            "classement impossible" in str(suivi.get(row, "Dernière réponse") or "")
        # candidature faite autrement (formulaire, La Bonne Alternance, LinkedIn…) : réponses suivies, sans relance
        self.hors_mail = self.statut in HORS_MAIL
        self.derniere = as_date(suivi.get(row, "Dernière action"))
        self.mes_envois, self.depuis = [], None


def _relance_due(p, l):
    """Relance due (mise dans la file), ou « Sans réponse » après la dernière relance."""
    s = p.suivi
    nb = int(s.get(l.row, "Nb relances") or 0)
    prevue = as_date(s.get(l.row, "Relance prévue"))
    if l.statut in (MAIL, "Relancé") and nb < CFG["relances_max"] and prevue \
            and prevue <= prochain_ouvrable(p.aujourd_hui, inclus=False):
        if not l.mes_envois and commun.DEPUIS:   # mail d'origine envoyé avant la date choisie
            l.mes_envois = sorted(p.envois_complets().get(l.mail, []), key=lambda x: x[0])
        if l.mes_envois:
            p.a_relancer.append((l.row, l.mes_envois[-1]))
        else:  # mail d'origine pas dans « Éléments envoyés » (autre boîte, webmail...) : relance sans transfert
            d = as_date(s.get(l.row, "Date envoi")) or p.aujourd_hui
            p.a_relancer.append((l.row, (datetime(d.year, d.month, d.day), "", None)))
    elif l.statut == "Relancé" and nb >= CFG["relances_max"] and l.derniere \
            and date_relance(l.derniere) <= p.aujourd_hui:
        s.set(l.row, "Statut", "Sans réponse")
        say(f"   💤 {l.ent} : sans réponse après {nb} relance(s)")
        p.bilan["passée(s) en « Sans réponse »"] += 1


def _passer_en_revue(p, row):
    l = Ligne(p.suivi, row)
    if not (l.statut in STATUTS_ACTIFS or l.hors_mail or l.a_reclasser):
        return
    if not est_adresse(l.mail):
        if not l.hors_mail:
            return  # « linkedin », « labonnealternance »... : pas une adresse, pas de suivi mail
        l.mail = ""
    l.mes_envois = sorted(p.envois.get(l.mail, []), key=lambda x: x[0])
    envois.constater(p, l)
    if l.statut == "Brouillon":
        return
    l.depuis = as_date(p.suivi.get(row, "Date envoi")) or p.aujourd_hui
    if reponses.adresse_invalide(p, l) or reponses.reponses_recues(p, l):
        return
    _relance_due(p, l)


def mettre_a_jour(suivi, ol, relancer=True):
    """Lit la messagerie (envois, réponses, non-remises) et met le tableau à jour ; relancer=False : sans écrire
    les brouillons de relance dus (routine « Mails reçus »)."""
    say(f"📬 Lecture de {nom_messagerie()}...")
    p = Passage(suivi, ol)
    for row in list(suivi.rows()):
        _passer_en_revue(p, row)
    ailleurs.traiter(p)   # accusés de réception / réponses de candidatures faites hors de LM Agent
    say("📊 Bilan : " + (", ".join(f"{n} {quoi}" for quoi, n in p.bilan.items()) if p.bilan else
                         "rien de nouveau dans la messagerie depuis le dernier passage (les réponses déjà classées et "
                         "les accusés de réception automatiques ne changent pas le tableau)."))
    if not relancer:
        if p.a_relancer:
            say(f"   {len(p.a_relancer)} relance(s) due(s) : elles seront écrites par la routine « Relances »")
        return
    p.a_relancer.sort(key=lambda x: as_date(suivi.get(x[0], "Relance prévue")) or date.min)
    maxi = CFG.get("relances_max_par_jour", 5)
    if len(p.a_relancer) > maxi:
        say(f"   {len(p.a_relancer)} relances dues : {maxi} aujourd'hui, les autres les jours suivants")
    for row, (t, sujet, item) in p.a_relancer[:maxi]:
        preparer_relance(suivi, ol, row, t, sujet, item)
