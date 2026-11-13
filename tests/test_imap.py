"""Messagerie Gmail / IMAP (alternance/src/imap.py), avec un faux serveur IMAP en mémoire."""
import email
import imaplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import pytest

import commun
import imap


# --- fonctions utilitaires -------------------------------------------------------------------------
def test_date_imap():
    assert imap._date_imap(datetime(2026, 3, 5)) == "05-Mar-2026"
    assert imap._date_imap(datetime(2026, 12, 25)) == "25-Dec-2026"


def test_date_locale():
    d = imap._date_locale("Fri, 13 Nov 2026 09:30:45 +0000")
    assert d.tzinfo is None and d.second == 0
    assert imap._date_locale("pas une date") is None
    assert imap._date_locale(None) is None


def test_adresses():
    assert imap._adresses("Jean <Jean@Exemple.fr>, rh@exemple.fr", None, "Paul <paul@x.fr>") == \
        ["jean@exemple.fr", "rh@exemple.fr", "paul@x.fr"]
    assert imap._adresses(None, "") == []
    assert imap._adresses("Sans adresse") == []


def test_decoder():
    assert imap._decoder("=?utf-8?q?Candidature_=C3=A0_Lyon?=") == "Candidature à Lyon"
    assert imap._decoder("Simple") == "Simple"
    assert imap._decoder(None) == ""


def message(texte=None, page=None, piece=None, **entetes):
    m = EmailMessage()
    for k, v in entetes.items():
        m[k.replace("_", "-")] = v
    if texte is not None:
        m.set_content(texte)
    if page is not None:
        if texte is None:
            m.set_content(page, subtype="html")
        else:
            m.add_alternative(page, subtype="html")
    if piece:
        m.add_attachment(piece, maintype="application", subtype="pdf", filename="cv.pdf")
    return m


class TestTexte:
    def test_partie_texte(self):
        assert imap._texte(message("Bonjour", "<p>HTML</p>")).strip() == "Bonjour"

    def test_seulement_html(self):
        t = imap._texte(message(page="<style>x{}</style><p>Ligne 1<br>Ligne 2</p><script>y</script>&eacute;"))
        assert "Ligne 1\nLigne 2" in t and "x{}" not in t and "y" not in t and "é" in t

    def test_pieces_jointes_ignorees(self):
        assert imap._texte(message("Corps", piece=b"%PDF-1.4")).strip() == "Corps"

    def test_texte_en_html(self):
        assert "<p>HTML</p>" in imap._texte_en_html(message("t", "<p>HTML</p>"))
        assert "&lt;b&gt;" in imap._texte_en_html(message("<b>texte</b>"))


# --- faux serveur IMAP -----------------------------------------------------------------------------
class FauxServeur:
    """Assez d'IMAP pour le module : LIST, SELECT, UID SEARCH/FETCH/MOVE/COPY/STORE, APPEND, EXPUNGE."""
    def __init__(self, dossiers, gmail=True, move=True):
        self.dossiers = dossiers           # nom -> {uid: bytes}
        self.gmail, self.move = gmail, move
        self.choisi, self.lecture_seule, self.appends, self.efface = None, True, [], set()
        self.coupures = 0

    def login(self, adresse, mdp):
        if mdp != "bon":
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Envoy&AOk-s"',
                      b'(\\HasNoChildren \\Drafts) "/" "[Gmail]/Brouillons"', b'(\\All) "/" "[Gmail]/Tous"',
                      b'(\\Trash) "/" "[Gmail]/Corbeille"']

    def select(self, dossier, readonly=True):
        dossier = dossier.strip('"')      # le vrai serveur accepte les noms entre guillemets
        if dossier not in self.dossiers:
            return "NO", [b"inconnu"]
        self.choisi, self.lecture_seule = dossier, readonly
        return "OK", [b"1"]

    def uid(self, commande, *args):
        if self.coupures:
            self.coupures -= 1
            raise imaplib.IMAP4.abort("connexion coupée")
        boite = self.dossiers[self.choisi]
        c = commande.upper()
        if c == "SEARCH":
            if args[1:] == ("X-GM-RAW", '"in:scheduled"') and not self.gmail:
                raise imaplib.IMAP4.error("commande inconnue")
            return "OK", [" ".join(boite).encode()]
        if c == "FETCH":
            uids = list(boite) if args[0] == "1:*" else args[0].split(",")
            rep = []
            for u in uids:
                brut = boite[u]
                if "HEADER.FIELDS" in args[1]:
                    brut = brut.split(b"\n\n")[0] + b"\n\n"
                elif "<0." in args[1]:
                    brut = brut[: int(args[1].split("<0.")[1].split(">")[0])]
                rep += [(f"{u} (UID {u} BODY[] {{{len(brut)}}}".encode(), brut), b")"]
            return "OK", rep
        if c == "MOVE":
            if not self.move:
                return "NO", [b"MOVE inconnu"]
            for u in args[0].split(","):
                self.dossiers[args[1].strip('"')][u] = boite.pop(u)
            return "OK", [b""]
        if c == "COPY":
            for u in args[0].split(","):
                self.dossiers[args[1].strip('"')][u] = boite[u]
            return "OK", [b""]
        if c == "STORE":
            self.efface |= set(args[0].split(","))
            return "OK", [b""]
        raise AssertionError(commande)

    def expunge(self):
        for u in self.efface:
            self.dossiers[self.choisi].pop(u, None)
        self.efface = set()

    def append(self, dossier, drapeaux, date, brut):
        dossier = dossier.strip('"')
        self.appends.append((dossier, drapeaux, brut))
        self.dossiers[dossier][str(100 + len(self.appends))] = brut

    def shutdown(self):
        pass


def brut(**k):
    return message(k.pop("texte", "Corps du mail"), **k).as_bytes().replace(b"\r\n", b"\n")


@pytest.fixture
def boite(monkeypatch, cfg):
    cfg["messagerie"] = {"type": "imap", "imap": {"serveur": "imap.test", "port": 993, "adresse": "moi@gmail.com",
                                                 "mot_de_passe_app": "bon", "signature_html": ""}}
    maintenant = format_datetime(datetime.now().astimezone() - timedelta(days=1))
    serveur = FauxServeur({
        "INBOX": {"1": brut(From="Jean <jean@exemple.fr>", Subject="Re: candidature", Date=maintenant, texte="Réponse"),
                  "2": brut(From="MAILER-DAEMON@x.fr", Subject="Undelivered", Date=maintenant)},
        "[Gmail]/Envoy&AOk-s": {"5": brut(To="jean@exemple.fr", Cc="rh@exemple.fr", Subject="Candidature",
                                          Date=maintenant)},
        "[Gmail]/Brouillons": {"7": brut(To="patron@boite.fr", Subject="Brouillon", texte="Texte du brouillon"),
                               "8": brut(To="autre@boite.fr", Subject="=?utf-8?q?R=C3=A9ponse?= ")},
        "[Gmail]/Tous": {"9": brut(To="programme@boite.fr", Subject="Plus tard")},
        "[Gmail]/Corbeille": {},
    })
    monkeypatch.setattr(imap.imaplib, "IMAP4_SSL", lambda *a, **k: serveur)
    b = imap.Imap()
    b.serveur = serveur
    return b


class TestImap:
    def test_mauvais_mot_de_passe(self, boite, cfg, monkeypatch):
        cfg["messagerie"]["imap"]["mot_de_passe_app"] = "faux"
        with pytest.raises(SystemExit) as e:
            imap.Imap()
        assert "mot de passe d'application" in str(e.value)

    def test_dossiers_speciaux(self, boite):
        d = {k: v.strip('"') for k, v in boite.dossiers.items()}
        assert d == {"recus": "INBOX", "envoyes": "[Gmail]/Envoy&AOk-s", "brouillons": "[Gmail]/Brouillons",
                     "tous": "[Gmail]/Tous", "corbeille": "[Gmail]/Corbeille"}

    def test_envois(self, boite):
        e = boite.envois(30)
        assert set(e) == {"jean@exemple.fr", "rh@exemple.fr"}
        t, sujet, mail = e["jean@exemple.fr"][0]
        assert sujet == "Candidature" and isinstance(t, datetime)
        assert "Corps du mail" in mail.Body

    def test_recus_et_non_remises(self, boite):
        r = boite.recus(30)
        par_sujet = {m["sujet"]: m for m in r}
        assert par_sujet["Re: candidature"]["de"] == "jean@exemple.fr"
        assert par_sujet["Re: candidature"]["classe"] == "IPM.Note"
        assert par_sujet["Undelivered"]["classe"] == "REPORT.NDR" and par_sujet["Undelivered"]["de"] == ""
        assert "Réponse" in par_sujet["Re: candidature"]["corps"]      # corps lu à la demande
        assert boite.recus(10) == r                                       # relu depuis le cache

    def test_destinataires_brouillons(self, boite):
        assert boite.destinataires_brouillons() == {"patron@boite.fr", "autre@boite.fr"}

    def test_programmes_gmail(self, boite):
        assert boite.programmes() == {"programme@boite.fr": None}
        assert boite.voit_programmes is True

    def test_programmes_autre_messagerie(self, boite):
        boite.serveur.gmail = False
        boite.voit_programmes = False
        assert boite.programmes() == {}
        assert boite.voit_programmes is False

    def test_textes_brouillons_en_une_requete(self, boite):
        t = sorted(boite.textes_brouillons())
        assert t[0][0] == "Brouillon" and t[0][1].strip() == "Texte du brouillon" and t[0][2] == ["patron@boite.fr"]
        assert t[1][0] == "Réponse" and t[1][2] == ["autre@boite.fr"]     # sujet décodé, espaces retirés

    def test_supprimer_brouillons_vers_la_corbeille(self, boite):
        assert boite.supprimer_brouillons("Patron@Boite.fr") == 1
        assert "7" not in boite.serveur.dossiers["[Gmail]/Brouillons"]
        assert "7" in boite.serveur.dossiers["[Gmail]/Corbeille"]

    def test_supprimer_sans_move(self, boite):
        boite.serveur.move = False
        assert boite.supprimer_brouillons("patron@boite.fr") == 1
        assert "7" in boite.serveur.dossiers["[Gmail]/Corbeille"]
        assert "7" not in boite.serveur.dossiers["[Gmail]/Brouillons"]

    def test_supprimer_rien_a_supprimer_ou_essai(self, boite):
        assert boite.supprimer_brouillons("inconnu@x.fr") == 0
        assert boite.supprimer_brouillons("") == 0
        commun.ESSAI = True
        assert boite.supprimer_brouillons("patron@boite.fr") == 0
        assert "7" in boite.serveur.dossiers["[Gmail]/Brouillons"]

    def test_brouillon_depose(self, boite, cfg):
        cfg["ajouter_signature"] = True
        boite.brouillon("rh@exemple.fr", "Candidature", "<p>Bonjour</p>")
        dossier, drapeaux, b = boite.serveur.appends[0]
        assert dossier == "[Gmail]/Brouillons" and drapeaux == "(\\Draft)"
        m = email.message_from_bytes(b, policy=email.policy.default)
        assert m["To"] == "rh@exemple.fr" and m["Subject"] == "Candidature" and m["From"] == "moi@gmail.com"
        assert "Camille Test" in m.get_body(("html",)).get_content()   # signature construite

    def test_brouillon_avec_pieces_jointes(self, boite, cfg, tmp_path):
        cv = tmp_path / "cv.pdf"
        cv.write_bytes(b"%PDF-1.4 cv")
        boite.brouillon("rh@exemple.fr", "Candidature", "<p>x</p>", pieces=[str(cv), str(tmp_path / "absent.pdf")])
        m = email.message_from_bytes(boite.serveur.appends[0][2], policy=email.policy.default)
        noms = [p.get_filename() for p in m.iter_attachments()]
        assert noms == ["cv.pdf"]

    def test_relance_cite_le_mail_d_origine(self, boite):
        _, _, origine = boite.envois(30)["jean@exemple.fr"][0]
        boite.brouillon("jean@exemple.fr", "Relance : Candidature", "<p>Je me permets</p>", base=origine)
        m = email.message_from_bytes(boite.serveur.appends[0][2], policy=email.policy.default)
        html = m.get_body(("html",)).get_content()
        assert "Message transféré" in html and "Corps du mail" in html and "Je me permets" in html

    def test_brouillon_en_mode_essai(self, boite):
        commun.ESSAI = True
        boite.brouillon("rh@exemple.fr", "x", "y")
        assert boite.serveur.appends == []

    def test_reconnexion_apres_coupure(self, boite):
        boite.serveur.coupures = 1
        assert boite.destinataires_brouillons() == {"patron@boite.fr", "autre@boite.fr"}

    def test_deux_coupures_d_affilee(self, boite):
        boite.serveur.coupures = 2
        with pytest.raises(imaplib.IMAP4.abort):
            boite.destinataires_brouillons()

    def test_dossier_brouillons_introuvable(self, boite, monkeypatch):
        monkeypatch.setattr(boite.serveur, "list", lambda: ("OK", [b'(\\HasNoChildren) "/" "INBOX"']))
        with pytest.raises(SystemExit):
            boite._dossiers_speciaux()

    def test_dossier_inaccessible(self, boite):
        with pytest.raises(RuntimeError):
            boite._choisir("N'existe pas")
