"""Bouton « Écrire ce qui manque » (web/src/redaction.py) : modèle et rédaction simulés, rien n'est lancé."""
import pytest

import lettres
import postuler
import redaction
import reponses
from tableau import FORMULAIRE, LBA


def ajouter(tableau, **v):
    tableau.add(**v)
    tableau.save()


def ligne(tableau, entreprise):
    from tableau import Suivi
    s = Suivi(tableau.path)
    return next(r[0].row for r in s.rows() if s.get(r, "Entreprise") == entreprise)


@pytest.fixture
def modele(monkeypatch):
    """Rédaction simulée : on note ce qui est demandé au modèle, et le déchargement final."""
    vu = {"lettres": [], "reponses": [], "decharge": 0}
    monkeypatch.setattr(postuler, "ecrire_lettre", lambda s, row: vu["lettres"].append(s.get(row, "Entreprise"))
                        or reponses.enregistrer_lettre(s.get(row, "Lien"), "Lettre écrite"))
    monkeypatch.setattr(postuler, "reponses_de", lambda s, row, deja: vu["reponses"].append(s.get(row, "Entreprise"))
                        or reponses.enregistrer(s.get(row, "Lien"), {"motivations": "M"}))
    import agent
    monkeypatch.setattr(agent, "liberer_modele", lambda: vu.__setitem__("decharge", vu["decharge"] + 1))
    monkeypatch.setattr(lettres, "lettres_et_signature", lambda: (reponses.lettres(), ""))
    return vu


@pytest.mark.parametrize("statut, lettre, reponses_ok, attendu", [
    (LBA, False, False, ["la lettre", "les réponses"]),
    (LBA, True, False, ["les réponses"]),
    (LBA, False, True, ["la lettre"]),
    (LBA, True, True, []),
    (FORMULAIRE, False, False, ["la lettre"]),          # formulaire du site : pas de questions
    (FORMULAIRE, True, False, []),
])
def test_ce_qui_manque(statut, lettre, reponses_ok, attendu):
    deja = {"https://x": {"motivations": "M"}} if reponses_ok else {}
    assert redaction.manque(statut, "https://x", lettre, deja) == attendu


def test_spontanee_lba_lettre_et_reponses(client, tableau, modele):
    ajouter(tableau, **{"Entreprise": "Spont", "Statut": LBA, "Poste": "Candidature spontanée", "Lien": "https://lba/s"})
    r = client.post("/api/ecrire", json={"ligne": ligne(tableau, "Spont"), "entreprise": "Spont"}).get_json()
    assert r["ok"] and "la lettre et les réponses" in r["message"]
    assert modele["lettres"] == ["Spont"] and modele["reponses"] == ["Spont"] and modele["decharge"] == 1
    assert reponses.lire()["https://lba/s"] == {"lettre": "Lettre écrite", "motivations": "M"}


def test_seulement_ce_qui_manque(client, tableau, modele):
    ajouter(tableau, **{"Entreprise": "A", "Statut": LBA, "Lien": "https://lba/a"})
    reponses.enregistrer_lettre("https://lba/a", "Déjà là")
    client.post("/api/ecrire", json={"ligne": ligne(tableau, "A"), "entreprise": "A"})
    assert modele["lettres"] == [] and modele["reponses"] == ["A"]


def test_rien_ne_manque(client, tableau, modele):
    ajouter(tableau, **{"Entreprise": "Site", "Statut": FORMULAIRE, "Lien": "https://site/c"})
    reponses.enregistrer_lettre("https://site/c", "Déjà là")
    r = client.post("/api/ecrire", json={"ligne": ligne(tableau, "Site"), "entreprise": "Site"}).get_json()
    assert r["ok"] and "rien ne manque" in r["message"] and modele["lettres"] == modele["reponses"] == []


def test_refus(client, tableau, modele, monkeypatch):
    ajouter(tableau, **{"Entreprise": "Mail", "Statut": "Brouillon", "Email": "rh@m.fr"})
    n = ligne(tableau, "Mail")
    assert client.post("/api/ecrire", json={"ligne": n, "entreprise": "Mail"}).status_code == 400   # pas un formulaire
    assert client.post("/api/ecrire", json={"ligne": n, "entreprise": "Autre"}).status_code == 400  # mauvaise ligne
    assert client.post("/api/ecrire", json={"ligne": "x"}).status_code == 400
    monkeypatch.setattr(redaction.routines, "en_cours", lambda: True)
    r = client.post("/api/ecrire", json={"ligne": n, "entreprise": "Mail"}).get_json()
    assert "routine" in r["message"]


def test_une_redaction_a_la_fois(client, tableau, modele):
    ajouter(tableau, **{"Entreprise": "A", "Statut": LBA, "Lien": "https://lba/a"})
    redaction.VERROU.acquire()
    try:
        r = client.post("/api/ecrire", json={"ligne": ligne(tableau, "A"), "entreprise": "A"}).get_json()
        assert not r["ok"] and "déjà en cours" in r["message"]
    finally:
        redaction.VERROU.release()


def test_modele_injoignable(client, tableau, modele, monkeypatch):
    ajouter(tableau, **{"Entreprise": "A", "Statut": LBA, "Lien": "https://lba/a"})

    def injoignable(s, row):
        raise SystemExit(1)       # agent.ensure_server quand LM Studio ne répond pas
    monkeypatch.setattr(postuler, "ecrire_lettre", injoignable)
    r = client.post("/api/ecrire", json={"ligne": ligne(tableau, "A"), "entreprise": "A"}).get_json()
    assert not r["ok"] and "LM Studio" in r["message"]
    assert modele["decharge"] == 1 and not redaction.VERROU.locked()       # tout est relâché


def test_bouton_sur_la_page(client, tableau, monkeypatch):
    monkeypatch.setattr(lettres, "lettres_et_signature", lambda: (reponses.lettres(), ""))
    ajouter(tableau, **{"Entreprise": "Spont", "Statut": LBA, "Poste": "Candidature spontanée", "Lien": "https://lba/s"})
    ajouter(tableau, **{"Entreprise": "Complet", "Statut": LBA, "Lien": "https://lba/c"})
    reponses.enregistrer("https://lba/c", {"lettre": "L", "motivations": "M"})
    h = client.get("/postuler").get_data(as_text=True)
    assert h.count("✍️ Écrire ce qui manque (") == 1
    assert "✍️ Écrire ce qui manque (la lettre et les réponses)" in h
    assert "python alternance" not in h                                        # plus de ligne de commande
