"""Messagerie par IMAP (Gmail et la plupart des messageries) : même rôle que outlook.py.

Lit les dossiers Envoyés / Boîte de réception / Brouillons sur le serveur et dépose les brouillons
dans le dossier Brouillons : tu les retrouves dans l'appli (PC, téléphone), tu relis et tu envoies
ou planifies toi-même. Le script n'envoie jamais rien.

Réglages (config_alternance.json) :
    "messagerie": {"type": "imap", "imap": {"serveur": "imap.gmail.com", "port": 993,
                   "adresse": "toi@gmail.com", "mot_de_passe_app": "xxxx xxxx xxxx xxxx",
                   "signature_html": "chemin/vers/signature.html"}}
"""
import email
import email.header
import email.policy
import html
import imaplib
import re
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid, parsedate_to_datetime

import commun
from commun import CFG, P, say

MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _date_imap(d):
    return f"{d.day:02d}-{MOIS[d.month - 1]}-{d.year}"


def _date_locale(valeur):
    """En-tête Date -> datetime locale sans fuseau (comme pour Outlook)."""
    try:
        d = parsedate_to_datetime(valeur)
        if d.tzinfo:
            d = d.astimezone().replace(tzinfo=None)
        return d.replace(second=0, microsecond=0)
    except Exception:
        return None


def _adresses(*valeurs):
    return [a.lower() for _, a in getaddresses([v for v in valeurs if v]) if "@" in a]


def _decoder(valeur):
    try:
        return str(email.header.make_header(email.header.decode_header(valeur or "")))
    except Exception:
        return valeur or ""


def _texte(msg):
    """Texte d'un mail : la partie texte si elle existe, sinon le HTML sans balises."""
    texte, page = "", ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_disposition() == "attachment":
            continue
        try:
            contenu = part.get_payload(decode=True)
            if contenu is None:
                continue
            contenu = contenu.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if part.get_content_type() == "text/plain" and not texte:
            texte = contenu
        elif part.get_content_type() == "text/html" and not page:
            page = contenu
    if texte:
        return texte
    page = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", page)
    return html.unescape(re.sub(r"<[^>]+>", "", page))


class MailImap:
    """Un mail du serveur ; son contenu complet n'est téléchargé que si on en a besoin."""
    def __init__(self, boite, dossier, uid, entetes):
        self._boite, self._dossier, self._uid, self._msg = boite, dossier, uid, None
        self.Subject = _decoder(entetes.get("Subject"))
        self.entetes = entetes

    def message(self):
        if self._msg is None:
            self._msg = self._boite.telecharger(self._dossier, self._uid)
        return self._msg

    @property
    def Body(self):  # même nom que dans Outlook : texte_mail() marche pour les deux
        return _texte(self.message())


class Recu(dict):
    """Mail reçu ; le corps n'est téléchargé que si on le demande (comme Msg dans outlook.py)."""
    def __init__(self, mail, **kw):
        super().__init__(**kw)
        self._mail = mail

    def __missing__(self, k):
        if k != "corps":
            raise KeyError(k)
        try:
            v = self._mail.Body[:4000]
        except Exception:
            v = ""
        self["corps"] = v
        return v


class Imap:
    # Mails programmés (« Programmer l'envoi ») : Gmail les retrouve avec la recherche « in:scheduled ».
    # Une autre messagerie IMAP ne les montre pas : un brouillon de relance disparu sans envoi est
    # alors supposé programmé plutôt que supprimé (voir suivi.py).
    voit_programmes = False  # passe à True si la recherche Gmail marche (voir programmes())

    def __init__(self):
        c = (CFG.get("messagerie") or {}).get("imap") or {}
        manque = [k for k in ("serveur", "adresse", "mot_de_passe_app") if not c.get(k)]
        if manque:
            raise SystemExit(f"❌ Messagerie IMAP : il manque {', '.join(manque)} dans "
                             "config_alternance.json (rubrique « messagerie » → « imap »)")
        self.adresse = c["adresse"]
        say(f"   Connexion à la messagerie {c['serveur']} ({self.adresse})...")
        self.cx = imaplib.IMAP4_SSL(c["serveur"], int(c.get("port", 993)), timeout=60)
        try:
            self.cx.login(self.adresse, c["mot_de_passe_app"])
        except imaplib.IMAP4.error as e:
            raise SystemExit(f"❌ Connexion refusée par {c['serveur']} ({e}). Pour Gmail : utilise un "
                             "« mot de passe d'application » (pas ton mot de passe normal), et active IMAP.")
        self.dossiers = self._dossiers_speciaux()
        self._cache_recus = None
        self._selectionne = None
        self.signature = ""
        sig = c.get("signature_html")
        if sig and P(sig).exists():
            self.signature = P(sig).read_text(encoding="utf-8", errors="replace")

    # --- outils ------------------------------------------------------------------------
    def _dossiers_speciaux(self):
        """Trouve Envoyés / Brouillons par leur rôle (\\Sent, \\Drafts) : le nom dépend de la langue."""
        trouves = {"recus": "INBOX"}
        _, lignes = self.cx.list()
        for l in lignes or []:
            l = l.decode(errors="replace")
            m = re.match(r'\((?P<drap>[^)]*)\) "(?P<sep>[^"]*)" (?P<nom>.+)$', l)
            if not m:
                continue
            nom = m.group("nom").strip()
            for drapeau, role in (("\\Sent", "envoyes"), ("\\Drafts", "brouillons"), ("\\All", "tous"),
                                  ("\\Trash", "corbeille")):
                if drapeau in m.group("drap"):
                    trouves[role] = nom
        for role in ("envoyes", "brouillons"):
            if role not in trouves:
                raise SystemExit(f"❌ Dossier « {role} » introuvable sur le serveur IMAP")
        return trouves

    def _choisir(self, dossier, lecture_seule=True):
        cle = (dossier, lecture_seule)
        if self._selectionne != cle:
            typ, _ = self.cx.select(dossier, readonly=lecture_seule)
            if typ != "OK":
                raise RuntimeError(f"dossier IMAP {dossier} inaccessible")
            self._selectionne = cle

    def _entetes(self, dossier, critere, champs):
        """[(uid, {en-tête: valeur})] des mails du dossier qui répondent au critère IMAP."""
        self._choisir(dossier)
        _, data = self.cx.uid("search", None, *([critere] if isinstance(critere, str) else critere))
        uids = (data[0] or b"").split()
        res = []
        for i in range(0, len(uids), 200):
            lot = b",".join(uids[i:i + 200]).decode()
            _, rep = self.cx.uid("fetch", lot, f"(UID BODY.PEEK[HEADER.FIELDS ({' '.join(champs)})])")
            for bloc in rep or []:
                if not isinstance(bloc, tuple):
                    continue
                m = re.search(rb"UID (\d+)", bloc[0])
                if m:
                    res.append((m.group(1).decode(), email.message_from_bytes(bloc[1])))
        return res

    def telecharger(self, dossier, uid):
        self._choisir(dossier)
        _, rep = self.cx.uid("fetch", uid, "(BODY.PEEK[])")
        brut = next((b[1] for b in rep or [] if isinstance(b, tuple)), b"")
        return email.message_from_bytes(brut, policy=email.policy.default)

    def _depuis(self, jours):
        return f"(SINCE {_date_imap(datetime.now() - timedelta(days=jours))})"

    # --- même interface que outlook.Outlook ------------------------------------------------
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
        d = self.dossiers["brouillons"]
        return [(m.Subject, m.Body, _adresses(h.get("To"), h.get("Cc"))) for m, h in
                ((MailImap(self, d, uid, h), h) for uid, h in self._entetes(d, "ALL", ["SUBJECT", "TO", "CC"]))]

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
        corps = f"<div style='font-family:Calibri,Arial,sans-serif;font-size:11pt'>{corps_html}</div><br>{self.signature}"
        a_joindre = []
        if base is not None:  # relance : le mail d'origine est cité en dessous, avec ses pièces jointes
            orig = base.message()
            h = base.entetes
            corps += ("<br><div style='border-top:1px solid #ccc;padding-top:8px;color:#555'>"
                      "---------- Message transféré ----------<br>"
                      f"<b>De :</b> {html.escape(self.adresse)}<br>"
                      f"<b>Date :</b> {html.escape(str(h.get('Date', '')))}<br>"
                      f"<b>Objet :</b> {html.escape(base.Subject)}<br>"
                      f"<b>À :</b> {html.escape(_decoder(h.get('To')))}<br><br>"
                      f"{_texte_en_html(orig)}</div>")
            for part in orig.iter_attachments():
                a_joindre.append((part.get_filename() or "piece_jointe", part.get_content_type(),
                                  part.get_payload(decode=True)))
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
        self.cx.append(self.dossiers["brouillons"], "(\\Draft)", imaplib.Time2Internaldate(time.time()),
                       msg.as_bytes())


def _texte_en_html(msg):
    """Corps HTML du mail d'origine s'il existe (rendu fidèle), sinon son texte."""
    try:
        partie = msg.get_body(preferencelist=("html", "plain"))
        contenu = partie.get_content()
        if partie.get_content_type() == "text/html":
            return re.sub(r"(?is)^.*?<body[^>]*>|</body>.*$", "", contenu)
        return html.escape(contenu).replace("\n", "<br>")
    except Exception:
        return ""
