"""Sites web des entreprises : trouver le site, puis une adresse mail ou un formulaire de contact.

1. Pas de site connu : on essaie les domaines évidents (nom.fr, nom.com, nom-en-tirets.fr…) en
   vérifiant que la page cite bien l'entreprise ; sinon recherche web (DuckDuckGo, version HTML),
   en gardant le premier résultat dont le domaine ressemble au nom (les annuaires sont écartés).
   Si DuckDuckGo répond par sa page anti-robot, on n'insiste pas jusqu'à la fin du passage.
2. Sur le site : page d'accueil, puis les pages « contact / recrutement / carrière » trouvées
   dans ses liens (et quelques adresses classiques). On y cherche :
   - une adresse affichée (y compris masquée : « [at] », protection Cloudflare) ;
   - un formulaire de contact (champ de message).
3. Seuls les sites d'entreprises en France sont gardés (réglage « sites.verifier_france », voir pays.py) :
   pas de site luxembourgeois, belge, américain… même si le nom correspond.

Ses modules s'appellent entre eux par `sites.X` (une fonction se remplace, dans les tests, à un seul endroit) :
    noms.py         mots qui distinguent une entreprise, domaine qui ressemble à son nom, ville d'une adresse
    pages.py        lecture d'une page web
    france.py       site d'une entreprise en France ?
    recherche.py    trouver le site (domaine deviné, sinon recherche web)
    exploration.py  adresse mail et formulaire de contact sur le site
"""
import time  # noqa: F401  (sites.time.sleep remplacé dans les tests)
import urllib.parse  # noqa: F401
import urllib.request  # noqa: F401  (sites.urllib.request.urlopen remplacé dans les tests)

from .pages import UA, _lire, _racine  # noqa: F401
from .noms import (ANNUAIRES, FORMES, JURIDIQUE, _mots, _mots_nom, _norm, _repere_lieu,  # noqa: F401
                   ressemble)
from .france import site_en_france, verifier_france  # noqa: F401
from .recherche import RECHERCHE, deviner_site, trouver_site  # noqa: F401
from .exploration import (GRAND_PUBLIC, MOTS_CONTACT, PAGES_CLASSIQUES, _a_un_formulaire, _adresses,  # noqa: F401
                          _cloudflare, _liens_contact, explorer_site)
