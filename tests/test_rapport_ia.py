"""Rapport rédigé par le modèle (web/src/rapport_ia.py, rapport_contexte.py, rapport_md.py) : modèle simulé."""
from datetime import date, timedelta

import pytest

import rapport
import rapport_contexte
import rapport_ia
import rapport_md
import redaction
import routines

AUJ = date.today()
LIGNES = [
    {"Entreprise": "Forgeval Dev", "Statut": "Candidaté (mail)", "Date envoi": AUJ - timedelta(days=8), "Nb relances": 1,
     "Relance prévue": AUJ + timedelta(days=2)},
    {"Entreprise": "Pixelo", "Statut": "Demande de disponibilités", "Date envoi": AUJ - timedelta(days=5),
     "Dernière action": AUJ - timedelta(days=1), "Dernière réponse": "2026-11-20 10:00 [disponibilites] Demande vos créneaux"},
    {"Entreprise": "Comptanova", "Statut": "À postuler (La Bonne Alternance)", "Date ajout": AUJ},
]


class Immediat:
    """Remplace threading.Thread : la rédaction se fait tout de suite (test sans attente)."""
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def modele_local(monkeypatch, faux_modele, tmp_path):
    import agent
    monkeypatch.setattr(rapport_ia, "dossier", lambda: tmp_path)        # rapports de ce test seulement
    vu = {"decharge": 0}
    monkeypatch.setattr(agent, "ensure_server", lambda *a, **k: None)
    monkeypatch.setattr(agent, "liberer_modele", lambda: vu.__setitem__("decharge", vu["decharge"] + 1))
    monkeypatch.setattr(rapport_ia.threading, "Thread", Immediat)
    monkeypatch.setattr(rapport_ia, "ETAT", {"etat": "inactif", "message": "", "fichier": ""})
    vu["faux"] = faux_modele
    return vu


def test_contexte_donne_toutes_les_infos():
    c = rapport_contexte.contexte(rapport.generer({"jours": "30"}, LIGNES))
    assert "Candidatures envoyées : 2" in c and "Pixelo (Demande de disponibilités) : 2026-11-20" in c
    assert "Forgeval Dev : envoyée le" in c and "1 relance(s)" in c              # sans réponse
    assert "Comptanova : À postuler (La Bonne Alternance)" in c                  # à finaliser
    assert "Relances prévues" in c and "Profil de l'étudiant" in c and "Activité des routines" in c


def test_redaction_enregistree_puis_modele_decharge(modele_local):
    modele_local["faux"].reponses_texte = ["# Rapport\n\n## Synthèse\n\n- **3** entreprises suivies"]
    ok, _ = rapport_ia.lancer({"jours": "7"}, LIGNES)
    assert ok and rapport_ia.ETAT["etat"] == "fini" and modele_local["decharge"] == 1
    nom = rapport_ia.ETAT["fichier"]
    assert nom in rapport_ia.enregistres() and "## Synthèse" in rapport_ia.lire(nom)
    assert "=== DONNÉES ===" in modele_local["faux"].consignes[0]
    assert not redaction.VERROU.locked()


def test_modele_injoignable(modele_local, monkeypatch):
    import agent

    def injoignable(*a, **k):
        raise SystemExit(1)
    monkeypatch.setattr(agent, "ensure_server", injoignable)
    assert rapport_ia.lancer({}, LIGNES)[0]
    assert rapport_ia.ETAT["etat"] == "erreur" and "ne répond pas" in rapport_ia.ETAT["message"]
    assert not redaction.VERROU.locked() and modele_local["decharge"] == 1


def test_refus_pendant_une_routine_ou_une_redaction(modele_local, monkeypatch):
    monkeypatch.setattr(routines, "en_cours", lambda: True)
    assert not rapport_ia.lancer({}, LIGNES)[0]
    monkeypatch.setattr(routines, "en_cours", lambda: False)
    with redaction.VERROU:
        assert not rapport_ia.lancer({}, LIGNES)[0]


def test_lire_refuse_les_chemins_hors_du_dossier():
    assert rapport_ia.lire("../config.json") == "" and rapport_ia.lire("rapport_x.txt") == ""


def test_markdown_sur():
    html = str(rapport_md.en_html("# Titre\n## Partie\nTexte **gras** <script>x</script>\n- un\n- deux\n\nFin"))
    assert "<h2>Titre</h2>" in html and "<h3>Partie</h3>" in html and "<b>gras</b>" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<ul>\n<li>un</li>\n<li>deux</li>\n</ul>" in html and "<p>Fin</p>" in html


def test_page_et_api(client, tableau, modele_local):
    tableau.save()
    assert "Aucun rapport rédigé" in client.get("/rapport").get_data(as_text=True)
    modele_local["faux"].reponses_texte = ["## Synthèse\nTout va bien."]
    r = client.post("/api/rapport/rediger", json={"jours": "30"})
    assert r.status_code == 200 and client.get("/api/rapport/etat").get_json()["etat"] == "fini"
    html = client.get("/rapport").get_data(as_text=True)
    assert "<h3>Synthèse</h3>" in html and "Rapport du " in html
