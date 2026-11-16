"""Socle commun des tests.

Garanties :
- aucune donnée réelle n'est lue ni écrite : dossier de données temporaire (LMAGENT_DONNEES) créé
  à partir des modèles *.example.*, tableau et journaux dans des fichiers temporaires ;
- aucun accès réseau : urllib est bloqué (un test qui a besoin d'une réponse la simule) ;
- aucun modèle IA, aucune messagerie, aucune tour : tout est remplacé par des faux objets ;
- la config est remise dans son état d'origine après chaque test.
"""
import atexit
import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
EXEMPLES = RACINE / "alternance" / "donnees"

# --- dossier de données temporaire, AVANT tout import du code ---------------------------------
TEMP = Path(tempfile.mkdtemp(prefix="lmagent_tests_"))
atexit.register(shutil.rmtree, TEMP, ignore_errors=True)   # supprimé à la fin des tests
DONNEES_TEST = TEMP / "donnees"
DONNEES_TEST.mkdir()
for exemple, reel in (("config_alternance.example.json", "config_alternance.json"),
                      ("profil.example.md", "profil.md"),
                      ("interdits.example.md", "interdits.md")):
    shutil.copy(EXEMPLES / exemple, DONNEES_TEST / reel)
_cfg = json.loads((DONNEES_TEST / "config_alternance.json").read_text(encoding="utf-8"))
_cfg["tableau_suivi"] = str(TEMP / "suivi_test.xlsx")
_cfg["pieces_jointes"] = []
_cfg["la_bonne_alternance"]["jeton_api"] = "jeton-de-test"
_cfg["messagerie"]["type"] = "outlook"
_cfg["signature_formulaire"] = {"nom": "Camille Test", "titre": "Étudiante", "telephone": "+33 6 00 00 00 00",
                                "email": "camille@exemple.fr", "linkedin": "https://linkedin.com/in/camille",
                                "portfolio": "", "github": ""}
_cfg["debut_signature"] = "Camille Test"
_cfg["domaines_ignores"] = ["mon-ecole.fr"]
(DONNEES_TEST / "config_alternance.json").write_text(json.dumps(_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
os.environ["LMAGENT_DONNEES"] = str(DONNEES_TEST)
os.environ["LMAGENT_DOSSIER"] = str(TEMP)   # config.json, journaux, workspace… temporaires aussi
# config.json de l'agent : installation déjà configurée (les tests de l'assistant repartent de zéro)
CONFIG_AGENT_TEST = {"assistant_a_faire": False, "utiliser_tour": False, "serveurs": [{"nom": "ce PC", "url": "local"}]}
(TEMP / "config.json").write_text(json.dumps(CONFIG_AGENT_TEST), encoding="utf-8")

for p in (RACINE / "alternance" / "src", RACINE / "alternance", RACINE / "web" / "src", RACINE / "web",
          RACINE / "src", RACINE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import agent  # noqa: E402
import commun  # noqa: E402

agent.LOGS = TEMP / "logs"          # journal de l'agent hors de logs/
agent.LOGS.mkdir(exist_ok=True)
CFG_ORIGINE = copy.deepcopy(commun.CFG)


# --- garde-fous automatiques -----------------------------------------------------------------
class ReseauInterdit(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch):
    """Tout appel réseau échoue : un test doit simuler les réponses dont il a besoin."""
    def refuse(*a, **k):
        raise ReseauInterdit("accès réseau interdit pendant les tests")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


@pytest.fixture(autouse=True)
def config_propre():
    """Config remise à l'identique et fichiers de données de test vidés après chaque test."""
    commun.CFG.clear()
    commun.CFG.update(copy.deepcopy(CFG_ORIGINE))
    commun.ESSAI = False
    yield
    commun.CFG.clear()
    commun.CFG.update(copy.deepcopy(CFG_ORIGINE))
    commun.ESSAI = False
    for nom in ("reponses_lba.json", "entreprises_refusees.csv", "acces_interface.json"):
        (DONNEES_TEST / nom).unlink(missing_ok=True)
    (TEMP / "config.json").write_text(json.dumps(CONFIG_AGENT_TEST), encoding="utf-8")
    agent.CONFIG.update(CONFIG_AGENT_TEST)
    (DONNEES_TEST / "config_alternance.json").write_text(json.dumps(CFG_ORIGINE, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    import auth
    auth.ECHECS.update(nb=0, jusqua=0.0)


@pytest.fixture
def cfg():
    return commun.CFG


@pytest.fixture
def tableau(tmp_path, cfg):
    """Tableau de suivi vide dans un fichier temporaire (créé avec les bonnes colonnes)."""
    from tableau import Suivi
    chemin = tmp_path / "suivi.xlsx"
    cfg["tableau_suivi"] = str(chemin)
    return Suivi(chemin)


@pytest.fixture
def faux_modele(monkeypatch):
    """Remplace le modèle IA : renvoie les réponses préparées et garde les consignes reçues."""
    class Faux:
        def __init__(self):
            self.consignes, self.reponses_json, self.reponses_texte = [], [], []

        def llm_json(self, prompt, system=None):
            self.consignes.append(prompt)
            r = self.reponses_json.pop(0) if self.reponses_json else {}
            if isinstance(r, Exception):
                raise r
            return r

        def llm(self, prompt, system=None):
            self.consignes.append(prompt)
            return self.reponses_texte.pop(0) if self.reponses_texte else "Bonjour,\n\nTexte du modèle.\n\nCordialement,"

    f = Faux()
    import candidatures
    import modele
    import sources
    import suivi
    for mod in (modele, candidatures, sources, suivi):
        if hasattr(mod, "llm_json"):
            monkeypatch.setattr(mod, "llm_json", f.llm_json)
        if hasattr(mod, "llm"):
            monkeypatch.setattr(mod, "llm", f.llm)
    return f


class FausseMessagerie:
    """Messagerie factice avec la même interface qu'Outlook / Imap."""
    voit_programmes = True

    def __init__(self, envois=None, recus=None, brouillons=None, programmes=None, textes=None):
        self._envois, self._recus = envois or {}, recus or []
        self._brouillons, self._programmes = set(brouillons or ()), dict(programmes or {})
        self._textes = textes or []
        self.deposes, self.supprimes = [], []

    def envois(self, jours=120):
        return self._envois

    def recus(self, jours=120):
        return self._recus

    def destinataires_brouillons(self):
        return self._brouillons

    def programmes(self):
        return self._programmes

    def textes_brouillons(self):
        return self._textes

    def brouillon(self, a, sujet, corps_html, pieces=(), envoi_differe=None, base=None):
        self.deposes.append({"a": a, "sujet": sujet, "corps": corps_html, "pieces": list(pieces), "base": base})

    def supprimer_brouillons(self, adresse):
        self.supprimes.append(adresse)
        return 1


@pytest.fixture
def messagerie():
    return FausseMessagerie


@pytest.fixture
def appli(monkeypatch, tmp_path):
    """Application web Flask de test, avec la vraie protection (Host local + jeton)."""
    import importlib.util
    import routines
    monkeypatch.setattr(routines, "LOGS", tmp_path / "logs")
    spec = importlib.util.spec_from_file_location("webapp", RACINE / "web" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "webapp", mod)   # Flask retrouve ainsi web/templates et web/static
    spec.loader.exec_module(mod)
    a = mod.creer_app()
    a.testing = True
    return a


IDENTIFIANT, MOT_DE_PASSE = "camille", "mot-de-passe-de-test"


@pytest.fixture
def anonyme(appli):
    """Client qui se présente comme le navigateur local, sans être connecté."""
    return _client(appli)


@pytest.fixture
def client(appli):
    """Client connecté (compte de test créé au premier lancement)."""
    c = _client(appli)
    r = c.post("/api/connexion", json={"identifiant": IDENTIFIANT, "mot_de_passe": MOT_DE_PASSE,
                                       "confirmation": MOT_DE_PASSE})
    assert r.status_code == 200, r.get_json()
    return c


def _client(appli):
    import securite

    class Client:
        """Client qui se présente comme le navigateur local (Host 127.0.0.1, jeton pour les POST)."""
        def __init__(self, c):
            self.c = c

        def get(self, url, **k):
            return self.c.get(url, headers={"Host": "127.0.0.1:8765"}, **k)

        def post(self, url, json=None, jeton=True, **k):
            h = {"Host": "127.0.0.1:8765"}
            if jeton:
                h["X-Jeton"] = securite.JETON
            return self.c.post(url, json=json, headers=h, **k)

    return Client(appli.test_client())
