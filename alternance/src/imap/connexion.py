"""Connexion au serveur IMAP : identifiants, reprise si le serveur coupe, dossiers spéciaux, lecture des en-têtes
et téléchargement des mails."""
import email
import email.policy
import imaplib
import re
import time
from datetime import datetime, timedelta

from commun import CFG, say
from .texte import _date_imap

ESSAIS_RESEAU, PAUSE_RESEAU = 4, 20   # 1 essai + 3 nouveaux essais à 20 s d'intervalle


class Connexion:
    def __init__(self):
        c = (CFG.get("messagerie") or {}).get("imap") or {}
        manque = [k for k in ("serveur", "adresse", "mot_de_passe_app") if not c.get(k)]
        if manque:
            raise SystemExit(f"❌ Messagerie IMAP : il manque {', '.join(manque)} dans "
                             "config_alternance.json (rubrique « messagerie » → « imap »)")
        self.adresse = c["adresse"]
        self._reglages = c
        say(f"   Connexion à la messagerie {c['serveur']} ({self.adresse})...")
        self._connecter()
        self.dossiers = self._dossiers_speciaux()
        self._cache_recus = None
        self.fichier_signature = c.get("signature_html") or ""  # vide : signature construite (voir commun)

    def _connecter(self):
        c = self._reglages
        for essai in range(1, ESSAIS_RESEAU + 1):
            try:
                self.cx = imaplib.IMAP4_SSL(c["serveur"], int(c.get("port", 993)), timeout=60)
                break
            except OSError as e:   # pas d'Internet (serveur introuvable), coupure, délai dépassé
                if essai == ESSAIS_RESEAU:
                    raise SystemExit(f"❌ Pas d'accès à {c['serveur']} ({e}) : vérifie ta connexion Internet "
                                     "puis relance la routine.")
                say(f"   🔌 {c['serveur']} injoignable ({e}) : nouvel essai dans {PAUSE_RESEAU} s "
                    f"({essai}/{ESSAIS_RESEAU - 1})...")
                time.sleep(PAUSE_RESEAU)
        try:
            self.cx.login(self.adresse, c["mot_de_passe_app"])
        except imaplib.IMAP4.error as e:
            raise SystemExit(f"❌ Connexion refusée par {c['serveur']} ({e}). Pour Gmail : utilise un "
                             "« mot de passe d'application » (pas ton mot de passe normal), et active IMAP.")
        self._selectionne = None

    def _avec_reprise(self, action):
        """Exécute action() ; si le serveur a coupé la connexion (Gmail ferme celles qui restent
        inactives pendant que le modèle écrit les lettres), se reconnecte et réessaie une fois."""
        try:
            return action()
        except (imaplib.IMAP4.abort, OSError) as e:
            say(f"   🔌 Connexion à la messagerie coupée ({e}) : reconnexion...")
            try:
                self.cx.shutdown()
            except Exception:
                pass
            self._connecter()
            return action()

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
        return self._avec_reprise(lambda: self._entetes_sans_reprise(dossier, critere, champs))

    def _entetes_sans_reprise(self, dossier, critere, champs):
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

    def telecharger(self, dossier, uid, maxi=None):
        """Message complet, ou seulement ses maxi premiers octets (assez pour le texte)."""
        def lire():
            self._choisir(dossier)
            return self.cx.uid("fetch", uid, f"(BODY.PEEK[]<0.{maxi}>)" if maxi else "(BODY.PEEK[])")
        _, rep = self._avec_reprise(lire)
        brut = next((b[1] for b in rep or [] if isinstance(b, tuple)), b"")
        return email.message_from_bytes(brut, policy=email.policy.default)

    def _depuis(self, jours):
        return f"(SINCE {_date_imap(datetime.now() - timedelta(days=jours))})"
