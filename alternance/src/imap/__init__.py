"""Messagerie par IMAP (Gmail et la plupart des messageries) : même rôle que outlook.py.

Lit les dossiers Envoyés / Boîte de réception / Brouillons sur le serveur et dépose les brouillons
dans le dossier Brouillons : tu les retrouves dans l'appli (PC, téléphone), tu relis et tu envoies
ou planifies toi-même. Le script n'envoie jamais rien.

Réglages (config_alternance.json) :
    "messagerie": {"type": "imap", "imap": {"serveur": "imap.gmail.com", "port": 993,
                   "adresse": "toi@gmail.com", "mot_de_passe_app": "xxxx xxxx xxxx xxxx",
                   "signature_html": "chemin/vers/signature.html"}}
    "ajouter_signature": true  -> signature sous les brouillons (fichier ci-dessus, ou vide = construite
                                  depuis "signature_formulaire" ; voir commun.signature_mail)

    texte.py       dates, adresses, en-têtes et texte d'un mail
    objets.py      un mail du serveur (téléchargé seulement si besoin), un mail reçu
    connexion.py   connexion (avec reprise si le serveur coupe), dossiers, en-têtes, téléchargement
    lecture.py     envois, mails reçus, brouillons, mails programmés
    brouillons.py  dépôt et suppression de brouillons
    etiquettes.py  libellé Gmail « Adresse à trouver » sur les brouillons sans vraie adresse
"""
import imaplib  # noqa: F401  (imap.imaplib.IMAP4_SSL remplacé par un faux serveur dans les tests)

from .brouillons import Brouillons
from .connexion import Connexion
from .etiquettes import Etiquettes, utf7_imap  # noqa: F401
from .lecture import Lecture
from .objets import MailImap, Recu  # noqa: F401
from .texte import MOIS, _adresses, _date_imap, _date_locale, _decoder, _texte, _texte_en_html  # noqa: F401


class Imap(Connexion, Lecture, Brouillons, Etiquettes):
    """Même interface que outlook.Outlook (envois, recus, brouillon…)."""
    # Mails programmés (« Programmer l'envoi ») : Gmail les retrouve avec la recherche « in:scheduled ».
    # Une autre messagerie IMAP ne les montre pas : un brouillon de relance disparu sans envoi est
    # alors supposé programmé plutôt que supprimé (voir suivi/).
    voit_programmes = False  # passe à True si la recherche Gmail marche (voir programmes())
