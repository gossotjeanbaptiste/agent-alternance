"""Lecture de la messagerie IMAP, avec la même interface que outlook.Outlook : envois, mails reçus,
destinataires et textes des brouillons, mails programmés (Gmail)."""
import email
import email.policy
import re
from datetime import datetime, timedelta

from commun import say
from .objets import MailImap, Recu
from .texte import _adresses, _date_locale, _decoder, _texte


class Lecture:
    def envois(self, jours=120):
        """{adresse: [(date, sujet, mail), ...]} des mails envoyés."""
        d = self.dossiers["envoyes"]
        res = {}
        lus = self._entetes(d, self._depuis(jours), ["TO", "CC", "DATE", "SUBJECT"])
        for uid, h in lus:
            t = _date_locale(h.get("Date"))
            if not t:
                continue
            mail = MailImap(self, d, uid, h)
            for a in _adresses(h.get("To"), h.get("Cc")):
                res.setdefault(a, []).append((t, mail.Subject, mail))
        say(f"   {len(lus)} mails envoyés lus ({jours} derniers jours)")
        return res

    def recus(self, jours=120):
        """Mails reçus (avec les avis de non-remise), gardés en cache."""
        mini = datetime.now() - timedelta(days=jours)
        if self._cache_recus and self._cache_recus[0] <= mini:
            return [m for m in self._cache_recus[1] if m["date"] >= mini]
        out = []
        for uid, h in self._entetes("INBOX", self._depuis(jours), ["FROM", "DATE", "SUBJECT", "CONTENT-TYPE"]):
            t = _date_locale(h.get("Date"))
            if not t or t < mini:
                continue
            de = (_adresses(h.get("From")) or [""])[0]
            ndr = "report" in (h.get("Content-Type") or "").lower() or \
                re.match(r"(mailer-daemon|postmaster)@", de)
            out.append(Recu(MailImap(self, "INBOX", uid, h), id=uid, date=t, sujet=_decoder(h.get("Subject")),
                            classe="REPORT.NDR" if ndr else "IPM.Note", de="" if ndr else de))
        out.sort(key=lambda m: m["date"], reverse=True)
        say(f"   {len(out)} mails reçus lus ({jours} derniers jours)")
        self._cache_recus = (mini, out)
        return out

    def destinataires_brouillons(self):
        return {a for _, h in self._entetes(self.dossiers["brouillons"], "ALL", ["TO", "CC"])
                for a in _adresses(h.get("To"), h.get("Cc"))}

    def programmes(self):
        """{adresse: None} des mails programmés (Gmail seulement ; l'heure prévue n'est pas lisible)."""
        if "tous" not in self.dossiers:
            return {}
        try:
            lus = self._entetes(self.dossiers["tous"], ("X-GM-RAW", '"in:scheduled"'), ["TO", "CC"])
        except Exception:
            return {}  # pas Gmail : on garde la supposition (voit_programmes reste False)
        self.voit_programmes = True
        return {a: None for _, h in lus for a in _adresses(h.get("To"), h.get("Cc"))}

    def textes_brouillons(self):
        """[(sujet, texte, [destinataires])] des brouillons (pour la page « À postuler »)."""
        # Une seule requête pour tous les brouillons (un aller-retour par mail coûtait ~0,8 s chacun),
        # et seulement le début de chaque mail : le texte, sans les pièces jointes.
        d = self.dossiers["brouillons"]
        self._choisir(d)
        _, rep = self.cx.uid("fetch", "1:*", "(UID BODY.PEEK[]<0.200000>)")
        res = []
        for bloc in rep or []:
            if not isinstance(bloc, tuple):
                continue
            msg = email.message_from_bytes(bloc[1], policy=email.policy.default)
            res.append((_decoder(msg.get("Subject")).strip(), _texte(msg), _adresses(msg.get("To"), msg.get("Cc"))))
        return res
