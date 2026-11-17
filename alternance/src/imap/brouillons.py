"""Brouillons IMAP : dépôt dans le dossier Brouillons (jamais d'envoi), relance avec le mail d'origine cité et ses
pièces jointes, mise à la corbeille des brouillons d'une adresse."""
import html
import imaplib
import re
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import commun
from commun import P, say
from .texte import _adresses, _decoder, _texte_en_html


class Brouillons:
    def supprimer_brouillons(self, adresse):
        """Met à la corbeille les brouillons adressés à cette adresse. Renvoie leur nombre."""
        adresse = (adresse or "").strip().lower()
        if not adresse or commun.ESSAI:
            return 0
        d = self.dossiers["brouillons"]
        uids = [uid for uid, h in self._entetes(d, "ALL", ["TO", "CC"]) if adresse in _adresses(h.get("To"), h.get("Cc"))]
        if not uids:
            return 0
        self._choisir(d, lecture_seule=False)
        lot = ",".join(uids)
        corbeille = self.dossiers.get("corbeille")
        if corbeille:
            typ, _ = self.cx.uid("MOVE", lot, corbeille)
            if typ != "OK":  # serveur sans MOVE : copie dans la corbeille puis effacement
                self.cx.uid("COPY", lot, corbeille)
                corbeille = None
        if not corbeille:
            self.cx.uid("STORE", lot, "+FLAGS", "(\\Deleted)")
            self.cx.expunge()
        return len(uids)

    def _citer(self, base):
        """Relance : le mail d'origine cité en dessous (HTML) et ses pièces jointes [(nom, type, données)]."""
        orig = base.message()
        h = base.entetes
        cite = ("<br><div style='border-top:1px solid #ccc;padding-top:8px;color:#555'>"
                "---------- Message transféré ----------<br>"
                f"<b>De :</b> {html.escape(self.adresse)}<br>"
                f"<b>Date :</b> {html.escape(str(h.get('Date', '')))}<br>"
                f"<b>Objet :</b> {html.escape(base.Subject)}<br>"
                f"<b>À :</b> {html.escape(_decoder(h.get('To')))}<br><br>"
                f"{_texte_en_html(orig)}</div>")
        pieces = [(part.get_filename() or "piece_jointe", part.get_content_type(), part.get_payload(decode=True))
                  for part in orig.iter_attachments()]
        return cite, pieces

    def brouillon(self, a, sujet, corps_html, pieces=(), envoi_differe=None, base=None):
        if commun.ESSAI:
            say(f"   [essai] brouillon -> {a or '(sans destinataire)'} : {sujet}")
            return
        msg = EmailMessage()
        msg["From"] = self.adresse
        if a:
            msg["To"] = a
        msg["Subject"] = sujet
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        corps = f"<div style='font-family:Calibri,Arial,sans-serif;font-size:11pt'>{corps_html}</div><br>{commun.signature_mail(self.fichier_signature)}"
        a_joindre = []
        if base is not None:  # relance : le mail d'origine est cité en dessous, avec ses pièces jointes
            cite, a_joindre = self._citer(base)
            corps += cite
        texte = re.sub(r"<[^>]+>", "", corps.replace("<br>", "\n").replace("</p>", "\n\n"))
        msg.set_content(html.unescape(texte))
        msg.add_alternative(f"<html><body>{corps}</body></html>", subtype="html")
        for p in pieces:
            if P(p).exists():
                a_joindre.append((P(p).name, "application/pdf" if P(p).suffix.lower() == ".pdf"
                                  else "application/octet-stream", P(p).read_bytes()))
        for nom, typ, donnees in a_joindre:
            if donnees:
                principal, _, sous = typ.partition("/")
                msg.add_attachment(donnees, maintype=principal, subtype=sous or "octet-stream", filename=nom)
        brut = msg.as_bytes()
        self._avec_reprise(lambda: self.cx.append(self.dossiers["brouillons"], "(\\Draft)",
                                                  imaplib.Time2Internaldate(time.time()), brut))
