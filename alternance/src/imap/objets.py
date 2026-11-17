"""Un mail du serveur, dont le contenu n'est téléchargé que si on en a besoin ; un mail reçu (comme dans outlook.py)."""
from .texte import _decoder, _texte


class MailImap:
    """Un mail du serveur ; son contenu complet n'est téléchargé que si on en a besoin."""
    def __init__(self, boite, dossier, uid, entetes):
        self._boite, self._dossier, self._uid, self._msg, self._debut = boite, dossier, uid, None, None
        self.Subject = _decoder(entetes.get("Subject"))
        self.entetes = entetes

    def message(self):
        if self._msg is None:
            self._msg = self._boite.telecharger(self._dossier, self._uid)
        return self._msg

    @property
    def Body(self):  # même nom que dans Outlook : texte_mail() marche pour les deux
        # Le texte est au début du mail, les pièces jointes (CV, PDF…) après : on ne télécharge
        # que le début, sinon chaque brouillon coûte ~1 s (le message complet sert aux relances).
        if self._msg is not None:
            return _texte(self._msg)
        if self._debut is None:
            self._debut = self._boite.telecharger(self._dossier, self._uid, maxi=200_000)
        return _texte(self._debut)


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
