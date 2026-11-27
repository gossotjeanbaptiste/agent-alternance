"""Libellé Gmail « Adresse à trouver » sur les brouillons sans vraie adresse (réglage messagerie.etiquette_a_trouver).

Posé à la création du brouillon, puis remis d'aplomb à chaque routine (etiqueter_brouillons) : ajouté aux brouillons
adressés à une adresse de remplacement (…@….invalid), retiré de ceux qui ont reçu leur vraie adresse. Les autres
brouillons sont donc prêts à partir. Gmail seulement (extension X-GM-EXT-1) ; une erreur ici ne fait jamais perdre
le brouillon : elle est seulement notée dans le journal.
"""
import base64
import re

import commun
from commun import say
from mails import est_a_trouver, etiquette_a_trouver
from .texte import _adresses


def utf7_imap(texte):
    """Nom de dossier / libellé en UTF-7 modifié (RFC 3501) : « Adresse à trouver » -> « Adresse &AOA- trouver »."""
    res, tampon = [], []

    def vider():
        if tampon:
            b64 = base64.b64encode("".join(tampon).encode("utf-16-be")).decode().rstrip("=")
            res.append("&" + b64.replace("/", ",") + "-")
            tampon.clear()
    for c in texte:
        if 0x20 <= ord(c) <= 0x7E:
            vider()
            res.append("&-" if c == "&" else c)
        else:
            tampon.append(c)
    vider()
    return "".join(res)


def _entre_guillemets(texte):
    return '"' + texte.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Etiquettes:
    def _libelle_gmail(self):
        """Libellé prêt pour une commande IMAP (encodé, entre guillemets), ou "" (réglage vide, pas Gmail)."""
        nom = etiquette_a_trouver()
        if not nom or "X-GM-EXT-1" not in getattr(self.cx, "capabilities", ()):
            return ""
        libelle = _entre_guillemets(utf7_imap(nom))
        if not getattr(self, "_libelle_cree", False):
            try:
                self.cx.create(libelle)   # déjà là : le serveur répond NO, sans conséquence
            except Exception:
                pass
            self._libelle_cree = True
        return libelle

    def _poser(self, uids, libelle, ajouter=True):
        d = self.dossiers["brouillons"]

        def faire():
            self._choisir(d, lecture_seule=False)
            self.cx.uid("STORE", ",".join(uids), "+X-GM-LABELS" if ajouter else "-X-GM-LABELS", f"({libelle})")
        self._avec_reprise(faire)

    def etiqueter_brouillon(self, reponse_append):
        """Libellé sur le brouillon qui vient d'être déposé (UID donné par le serveur : « APPENDUID v uid »)."""
        try:
            libelle = self._libelle_gmail()
            if not libelle:
                return
            texte = b" ".join(x for x in (reponse_append or [b""]) if isinstance(x, bytes))
            m = re.search(rb"APPENDUID \d+ (\d+)", texte)
            if m:
                self._poser([m.group(1).decode()], libelle)
            else:
                self.etiqueter_brouillons()
        except Exception as e:
            say(f"   ⚠️ Étiquette « {etiquette_a_trouver()} » non posée ({e}) : le brouillon est bien là")

    def etiqueter_brouillons(self):
        """Remet les libellés d'aplomb sur tous les brouillons. Renvoie (ajoutés, retirés)."""
        if commun.ESSAI:
            return 0, 0
        try:
            libelle = self._libelle_gmail()
            if not libelle:
                return 0, 0
            d = self.dossiers["brouillons"]
            a_trouver = {uid for uid, h in self._entetes(d, "ALL", ["TO", "CC"])
                         if any(est_a_trouver(a) for a in _adresses(h.get("To"), h.get("Cc")))}
            def chercher():
                self._choisir(d)
                return self.cx.uid("SEARCH", None, "X-GM-LABELS", libelle)
            _, data = self._avec_reprise(chercher)
            portent = set((data[0] or b"").decode().split()) if data else set()
            ajouter, retirer = sorted(a_trouver - portent), sorted(portent - a_trouver)
            if ajouter:
                self._poser(ajouter, libelle)
            if retirer:
                self._poser(retirer, libelle, ajouter=False)
            return len(ajouter), len(retirer)
        except Exception as e:
            say(f"   ⚠️ Étiquettes « {etiquette_a_trouver()} » non mises à jour ({e})")
            return 0, 0
