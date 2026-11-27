"""Messagerie Gmail / IMAP (alternance/src/imap/), avec un faux serveur IMAP en mémoire."""
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
        self.capabilities = ("IMAP4REV1", "UIDPLUS") + (("X-GM-EXT-1",) if gmail else ())
        self.libelles, self.crees, self.appenduid = {}, [], True   # uid -> {libellés}

    def create(self, nom):
        self.crees.append(nom)
        return "NO", [b"[ALREADYEXISTS] Duplicate folder name"]

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
            if args[1:2] == ("X-GM-LABELS",):
                return "OK", [" ".join(u for u in boite if args[2] in self.libelles.get(u, ())).encode()]
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
            assert not self.lecture_seule, "STORE sur un dossier ouvert en lecture seule"
            if args[1] in ("+X-GM-LABELS", "-X-GM-LABELS"):
                libelle = args[2][1:-1]   # « ("…") » -> « "…" »
                for u in args[0].split(","):
                    s = self.libelles.setdefault(u, set())
                    s.add(libelle) if args[1][0] == "+" else s.discard(libelle)
                return "OK", [b""]
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
        uid = str(100 + len(self.appends))
        self.dossiers[dossier][uid] = brut
        return "OK", [f"[APPENDUID 1 {uid}] (Success)".encode() if self.appenduid else b"(Success)"]

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

    def test_pas_d_internet_puis_retour(self, boite, monkeypatch):
        import socket
        import imap.connexion
        essais, pauses = [], []
        def connexion(*a, **k):
            essais.append(1)
            if len(essais) < 3:
                raise socket.gaierror(11001, "getaddrinfo failed")
            return boite.serveur
        monkeypatch.setattr(imap.imaplib, "IMAP4_SSL", connexion)
        monkeypatch.setattr(imap.connexion.time, "sleep", pauses.append)
        imap.Imap()
        assert len(essais) == 3 and pauses == [20, 20]

    def test_pas_d_internet_message_clair(self, boite, monkeypatch):
        import socket
        import imap.connexion
        def connexion(*a, **k):
            raise socket.gaierror(11001, "getaddrinfo failed")
        monkeypatch.setattr(imap.imaplib, "IMAP4_SSL", connexion)
        monkeypatch.setattr(imap.connexion.time, "sleep", lambda s: None)
        with pytest.raises(SystemExit) as e:
            imap.Imap()
        assert "connexion Internet" in str(e.value)

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

    def test_brouillon_a_plusieurs_adresses(self, boite):
        boite.brouillon("rh@exemple.fr; marc@exemple.fr", "Relance", "<p>x</p>")
        m = email.message_from_bytes(boite.serveur.appends[0][2], policy=email.policy.default)
        assert m["To"] == "rh@exemple.fr, marc@exemple.fr"           # séparées par une virgule dans un vrai mail

    def test_supprimer_brouillons_de_plusieurs_adresses(self, boite):
        assert boite.supprimer_brouillons("inconnu@x.fr; Patron@Boite.fr") == 1

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


# --- libellé « Adresse à trouver » (Gmail) ---------------------------------------------------------
A_TROUVER = '"Pixelo (adresse à trouver)" <a-trouver@pixelo.invalid>'
LIBELLE = '"Adresse &AOA- trouver"'


@pytest.mark.parametrize("texte, attendu", [
    ("Adresse à trouver", "Adresse &AOA- trouver"),
    ("Envoyés", "Envoy&AOk-s"),
    ("R&D", "R&-D"),
    ("Simple", "Simple"),
    ("été", "&AOk-t&AOk-"),
])
def test_utf7_imap(texte, attendu):
    assert imap.utf7_imap(texte) == attendu


class TestEtiquettes:
    def brouillons(self, boite):
        return boite.serveur.dossiers["[Gmail]/Brouillons"]

    def test_pose_a_la_creation(self, boite):
        boite.brouillon(A_TROUVER, "Candidature", "<p>x</p>")
        uid = max(self.brouillons(boite), key=int)
        assert boite.serveur.libelles[uid] == {LIBELLE}
        assert boite.serveur.crees == [LIBELLE]

    def test_pas_pose_sur_une_vraie_adresse(self, boite):
        boite.brouillon("rh@pixelo.fr", "Candidature", "<p>x</p>")
        assert boite.serveur.libelles == {}

    def test_sans_appenduid_passe_par_la_remise_en_ordre(self, boite):
        boite.serveur.appenduid = False
        boite.brouillon(A_TROUVER, "Candidature", "<p>x</p>")
        assert boite.serveur.libelles[max(self.brouillons(boite), key=int)] == {LIBELLE}

    def test_reglage_vide_pas_de_libelle(self, boite, cfg):
        cfg["messagerie"]["etiquette_a_trouver"] = ""
        boite.brouillon(A_TROUVER, "Candidature", "<p>x</p>")
        assert boite.serveur.libelles == {} and boite.serveur.crees == []
        assert boite.etiqueter_brouillons() == (0, 0)

    def test_pas_gmail_pas_de_libelle(self, boite):
        boite.serveur.capabilities = ("IMAP4REV1",)
        boite.brouillon(A_TROUVER, "Candidature", "<p>x</p>")
        assert boite.serveur.libelles == {} and len(boite.serveur.appends) == 1   # le brouillon est bien là

    def test_remise_en_ordre(self, boite):
        b = self.brouillons(boite)
        b["20"] = brut(To=A_TROUVER, Subject="Ancien brouillon sans adresse")           # libellé à poser
        b["21"] = brut(To="contact@comptanova.fr", Subject="Adresse renseignée depuis")   # libellé à retirer
        boite.serveur.libelles = {"21": {LIBELLE}, "7": {'"Autre"'}}
        assert boite.etiqueter_brouillons() == (1, 1)
        assert boite.serveur.libelles["20"] == {LIBELLE}
        assert boite.serveur.libelles["21"] == set() and boite.serveur.libelles["7"] == {'"Autre"'}
        assert boite.etiqueter_brouillons() == (0, 0)   # déjà en ordre : rien à refaire

    def test_rien_en_mode_essai(self, boite):
        self.brouillons(boite)["20"] = brut(To=A_TROUVER, Subject="x")
        commun.ESSAI = True
        assert boite.etiqueter_brouillons() == (0, 0) and boite.serveur.libelles == {}

    def test_une_erreur_ne_casse_rien(self, boite, monkeypatch, capsys):
        def refuse(*a):
            raise imaplib.IMAP4.error("STORE refusé")
        boite.brouillon("rh@pixelo.fr", "x", "y")
        monkeypatch.setattr(boite, "_poser", refuse)
        boite.brouillon(A_TROUVER, "Candidature", "<p>x</p>")
        assert len(boite.serveur.appends) == 2 and "non posée" in capsys.readouterr().out
