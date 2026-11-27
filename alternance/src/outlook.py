"""Lecture d'Outlook (classique, via COM) et création des brouillons."""
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import commun
import reglages
from commun import CFG, P, say
from mails import adresses, est_a_trouver, etiquette_a_trouver

def _chemins_outlook():
    """Emplacements possibles d'OUTLOOK.EXE (modifiables dans la page Paramètres, section « Messagerie »)."""
    return [Path(p) for p in reglages.valeur("outlook.chemins_exe")]


def _separateur_liste():
    """Séparateur de listes de Windows (« ; » en français) : Outlook l'utilise entre les catégories d'un mail."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as k:
            return winreg.QueryValueEx(k, "sList")[0] or ";"
    except Exception:
        return ";"


def categories_modifiees(actuelles, nom, ajouter, sep=";"):
    """Catégories d'un mail après ajout / retrait de nom, ou None si rien ne change."""
    liste = [c.strip() for c in re.split(r"[,;]", actuelles or "") if c.strip()]
    if (nom in liste) == ajouter:
        return None
    liste = liste + [nom] if ajouter else [c for c in liste if c != nom]
    return f"{sep} ".join(liste)


class Msg(dict):
    """Mail reçu ; le corps n'est lu dans Outlook que si on en a besoin (c'est ce qui est lent)."""
    def __init__(self, ns, **kw):
        super().__init__(**kw)
        self._ns = ns

    def __missing__(self, k):
        if k != "corps":
            raise KeyError(k)
        try:
            v = (self._ns.GetItemFromID(self["id"]).Body or "")[:4000]
        except Exception:
            v = ""
        self["corps"] = v
        return v


def _outlook_lance():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/NH"],
                       capture_output=True, text=True, errors="replace")
    return "OUTLOOK.EXE" in r.stdout.upper()


class Outlook:
    voit_programmes = True  # Boîte d'envoi et brouillons planifiés visibles

    def __init__(self):
        import win32com.client
        # Lancé caché par COM, Outlook ne peut pas afficher sa fenêtre de connexion et reste bloqué.
        # On l'ouvre donc normalement (fenêtre visible) s'il ne tourne pas déjà.
        if not _outlook_lance():
            exe = next((p for p in _chemins_outlook() if p.exists()), None)
            if exe:
                say("   Ouverture de l'Outlook classique (connecte-toi si une fenêtre le demande)...")
                subprocess.Popen([str(exe)])
                time.sleep(int(reglages.valeur("outlook.attente_ouverture_s")))
        self.app = win32com.client.Dispatch("Outlook.Application")
        self.ns = self.app.GetNamespace("MAPI")
        self.inbox = self.ns.GetDefaultFolder(6)
        self.sent = self.ns.GetDefaultFolder(5)
        self._cache_recus = None
        self._utc = datetime.now().astimezone().utcoffset()  # Outlook donne les heures en UTC
        # Le nouvel Outlook ajoute déjà ta signature automatiquement à l'ouverture du brouillon :
        # dans ce cas laisser "ajouter_signature" à false, sinon elle apparaît deux fois.

    @staticmethod
    def _addr(entry_or_recipient):
        try:
            a = entry_or_recipient.Address or ""
            if "@" in a:
                return a.lower()
            ex = entry_or_recipient.AddressEntry.GetExchangeUser()
            if ex and "@" in (ex.PrimarySmtpAddress or ""):
                return ex.PrimarySmtpAddress.lower()
        except Exception:
            pass
        try:  # destinataire pas encore « résolu » (brouillon créé par script) : l'adresse est dans le nom
            n = (entry_or_recipient.Name or "").strip().strip("'\"<>")
            return n.lower() if "@" in n else ""
        except Exception:
            return ""

    def _recent(self, folder, champ, jours, limite=1500):
        items = folder.Items
        items.Sort(f"[{champ}]", True)
        mini = datetime.now() - timedelta(days=jours)
        for n, it in enumerate(items):
            if n >= limite:
                break
            try:
                t = getattr(it, champ)
                t = datetime(t.year, t.month, t.day, t.hour, t.minute)
            except Exception:
                continue
            if t < mini:
                break
            yield it, t

    def envois(self, jours=120):
        """{adresse: [(date, sujet, item), ...]} des mails envoyés."""
        res = {}
        n = 0
        for it, t in self._recent(self.sent, "SentOn", jours):
            n += 1
            try:
                for r in it.Recipients:
                    res.setdefault(self._addr(r), []).append((t, it.Subject or "", it))
            except Exception:
                pass
        say(f"   {n} mails envoyés lus ({jours} derniers jours)")
        return res

    def recus(self, jours=120):
        """Mails reçus (avec les avis de non-remise). Lecture en bloc via la vue « Table »
        d'Outlook, bien plus rapide que d'ouvrir chaque mail ; résultat gardé en cache."""
        mini = datetime.now() - timedelta(days=jours)
        if self._cache_recus and self._cache_recus[0] <= mini:
            return [m for m in self._cache_recus[1] if m["date"] >= mini]
        out = []
        t = self.inbox.GetTable()
        t.Sort("[ReceivedTime]", True)
        cols = t.Columns
        cols.RemoveAll()
        for c in ("EntryID", "Subject", "ReceivedTime", "MessageClass", "SenderEmailAddress"):
            cols.Add(c)
        while not t.EndOfTable:
            eid, sujet, recu, cls, de = t.GetNextRow().GetValues()
            try:
                d = datetime(recu.year, recu.month, recu.day, recu.hour, recu.minute) + self._utc
            except Exception:
                continue
            if d < mini:
                break
            cls = cls or ""
            out.append(Msg(self.ns, id=eid, date=d, sujet=sujet or "", classe=cls,
                           de=(de or "").lower() if "REPORT" not in cls.upper() else ""))
        say(f"   {len(out)} mails reçus lus ({jours} derniers jours)")
        self._cache_recus = (mini, out)
        return out

    def _destinataires(self, num_dossier):
        res = {}
        try:
            for it in self.ns.GetDefaultFolder(num_dossier).Items:
                try:
                    quand = it.DeferredDeliveryTime
                    if quand.year > 4000:  # « pas de date » pour Outlook
                        quand = None
                    else:  # Outlook la donne en UTC : conversion en heure locale
                        quand = quand.astimezone() if quand.tzinfo else quand
                        quand = datetime(quand.year, quand.month, quand.day, quand.hour, quand.minute)
                except Exception:
                    quand = None
                try:
                    for r in it.Recipients:
                        res[self._addr(r)] = quand
                except Exception:
                    pass
        except Exception:
            pass
        return res

    def destinataires_brouillons(self):
        """Adresses des destinataires des brouillons (dossier Brouillons)."""
        return set(self._destinataires(16))

    def programmes(self):
        """{adresse: date d'envoi prévue} des mails que tu as planifiés, en attente de leur heure :
        - « Planifier l'envoi » du nouvel Outlook : le mail reste dans Brouillons, avec sa date d'envoi ;
        - envoi différé de l'Outlook classique : le mail attend dans la Boîte d'envoi."""
        res = {a: q for a, q in self._destinataires(16).items() if q}
        res.update(self._destinataires(4))
        return res

    def textes_brouillons(self):
        """[(sujet, texte, [destinataires])] des brouillons (pour la page « À postuler »)."""
        res = []
        for it in self.ns.GetDefaultFolder(16).Items:
            try:
                res.append((it.Subject or "", it.Body or "", [self._addr(r) for r in it.Recipients]))
            except Exception:
                pass
        return res

    def supprimer_brouillons(self, adresse):
        """Met à la corbeille (Éléments supprimés) les brouillons adressés à cette adresse. Renvoie leur nombre."""
        cibles = set(adresses(adresse))          # une ou plusieurs adresses (« a@x.fr; b@x.fr »)
        if not cibles or commun.ESSAI:
            return 0
        a_supprimer = []
        for it in self.ns.GetDefaultFolder(16).Items:  # on liste d'abord : supprimer en parcourant saute des mails
            try:
                if cibles & {self._addr(r) for r in it.Recipients}:
                    a_supprimer.append(it)
            except Exception:
                pass
        for it in a_supprimer:
            it.Delete()
        return len(a_supprimer)

    def brouillon(self, a, sujet, corps_html, pieces=(), envoi_differe=None, base=None):
        if commun.ESSAI:
            say(f"   [essai] brouillon -> {a or '(sans destinataire)'} : {sujet}")
            return
        mail = base.Forward() if base is not None else self.app.CreateItem(0)
        mail.To = a or ""
        try:
            mail.Recipients.ResolveAll()  # sinon le destinataire reste sans adresse et le brouillon est « introuvable »
        except Exception:
            pass
        mail.Subject = sujet
        ancien = mail.HTMLBody if base is not None else ""
        mail.HTMLBody = (f"<div style='font-family:Calibri,Arial,sans-serif;font-size:11pt'>{corps_html}</div>"
                         f"<br>{commun.signature_mail(CFG.get('signature_html'))}{ancien}")
        for p in pieces:
            if P(p).exists():
                mail.Attachments.Add(str(P(p)))
        if envoi_differe:
            mail.DeferredDeliveryTime = envoi_differe
        nom = etiquette_a_trouver()
        if nom and est_a_trouver(re.sub(r".*<|>.*", "", a or "")):
            self._categorie_existe(nom)
            mail.Categories = nom   # repérer d'un coup d'œil les brouillons dont l'adresse reste à trouver
        mail.Save()

    def _categorie_existe(self, nom):
        """Ajoute la catégorie à la liste d'Outlook (sinon elle s'affiche sans couleur)."""
        try:
            if not any(c.Name == nom for c in self.ns.Categories):
                self.ns.Categories.Add(nom, 2)   # 2 = orange
        except Exception:
            pass

    def etiqueter_brouillons(self):
        """Catégorie « Adresse à trouver » ajoutée aux brouillons sans vraie adresse, retirée de ceux qui l'ont
        reçue (réglage messagerie.etiquette_a_trouver). Renvoie (ajoutés, retirés)."""
        nom = etiquette_a_trouver()
        if not nom or commun.ESSAI:
            return 0, 0
        self._categorie_existe(nom)
        sep, compte = _separateur_liste(), [0, 0]
        for it in self.ns.GetDefaultFolder(16).Items:
            try:
                a_trouver = any(est_a_trouver(self._addr(r)) for r in it.Recipients)
                nouvelles = categories_modifiees(it.Categories, nom, a_trouver, sep)
                if nouvelles is not None:
                    it.Categories = nouvelles
                    it.Save()
                    compte[0 if a_trouver else 1] += 1
            except Exception:
                pass
        return tuple(compte)


def texte_mail(item, maxi=3500):
    """Texte d'un mail envoyé, sans la signature ni les longues lignes vides."""
    try:
        t = item.Body or ""
    except Exception:
        return ""
    debut = (CFG.get("debut_signature") or "").strip()  # ex. "Prénom NOM" : 1re ligne de ta signature
    i = t.replace("\r\n", "\n").find(debut + "\n") if debut else -1
    if i > 200:
        t = t.replace("\r\n", "\n")[:i]
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t.replace("\r\n", "\n")).strip()
    return t[:maxi]
