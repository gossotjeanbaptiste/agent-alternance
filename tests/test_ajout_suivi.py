"""Formulaire « Ajouter une candidature » de la page Suivi (suivi_donnees.ajouter, /api/suivi/ajouter)."""
from datetime import date

import pytest

import suivi_donnees
from tableau import Suivi


def lignes(tableau):
    s = Suivi(tableau.path)
    return {s.get(r, "Entreprise"): {c: s.get(r, c) for c in s.h} for r in s.rows()}


def jour(v):
    return v.date() if hasattr(v, "date") else v


def test_ajout_simple(client, tableau):
    tableau.save()
    r = client.post("/api/suivi/ajouter", json={"Entreprise": "Boîte", "Poste": "Dev", "Lieu": "69003 Lyon",
                                                "Statut": "Candidaté (autre canal)", "Source": "Salon / forum"})
    assert r.status_code == 200 and r.get_json()["ok"]
    l = lignes(tableau)["Boîte"]
    assert l["Statut"] == "Candidaté (autre canal)" and l["Source"] == "Salon / forum" and l["Nb relances"] == 0
    assert jour(l["Date ajout"]) == date.today() and jour(l["Date envoi"]) == date.today()
    assert l["Relance prévue"] in (None, "")                           # autre canal : pas de relance par mail


def test_candidature_par_mail_relance_prevue(client, tableau):
    tableau.save()
    client.post("/api/suivi/ajouter", json={"Entreprise": "Mail Co", "Email": "rh@mailco.fr",
                                            "Statut": "Candidaté (mail)", "Date envoi": "2026-11-02"})
    l = lignes(tableau)["Mail Co"]
    assert jour(l["Date envoi"]) == date(2026, 11, 2) and l["Relance prévue"] is not None
    assert l["Source"] == "Ajout manuel" and l["Email"] == "rh@mailco.fr"


def test_a_postuler_sans_date_d_envoi(client, tableau):
    tableau.save()
    client.post("/api/suivi/ajouter", json={"Entreprise": "Plus Tard", "Statut": "À postuler (formulaire du site)",
                                            "Lien": "https://plustard.fr/contact"})
    assert lignes(tableau)["Plus Tard"]["Date envoi"] in (None, "")


def test_doublon_signale_puis_force(client, tableau):
    tableau.add(**{"Entreprise": "Xefi", "Lieu": "69003 Lyon", "Statut": "Refus"})
    tableau.save()
    r = client.post("/api/suivi/ajouter", json={"Entreprise": "XEFI", "Lieu": "Lyon", "Statut": "Candidaté (autre canal)"})
    assert r.status_code == 400 and r.get_json()["doublon"] and "déjà dans le tableau" in r.get_json()["message"]
    r = client.post("/api/suivi/ajouter", json={"Entreprise": "XEFI", "Lieu": "Lyon", "Statut": "Candidaté (autre canal)",
                                                "forcer": True})
    assert r.get_json()["ok"]


def test_autre_etablissement_du_meme_nom(client, tableau):
    tableau.add(**{"Entreprise": "Xefi", "Lieu": "69003 Lyon", "Statut": "Refus"})
    tableau.save()
    r = client.post("/api/suivi/ajouter", json={"Entreprise": "Xefi", "Lieu": "38000 Grenoble",
                                                "Statut": "Candidaté (autre canal)"})
    assert r.get_json()["ok"]


@pytest.mark.parametrize("donnees, message", [
    ({"Entreprise": "", "Statut": "Refus"}, "nom de l'entreprise"),
    ({"Entreprise": "A", "Statut": "N'importe quoi"}, "Statut inconnu"),
    ({"Entreprise": "A", "Statut": "Refus", "Email": "pas une adresse"}, "invalide"),
    ({"Entreprise": "A", "Statut": "Refus", "Date envoi": "02/11/2026"}, "Date"),
])
def test_refus(client, tableau, donnees, message):
    tableau.save()
    r = client.post("/api/suivi/ajouter", json=donnees)
    assert r.status_code == 400 and message in r.get_json()["message"]
    assert lignes(tableau) == {}


def test_pendant_une_routine(tableau, monkeypatch):
    monkeypatch.setattr(suivi_donnees.routines, "en_cours", lambda: True)
    ok, message, _ = suivi_donnees.ajouter({"Entreprise": "A", "Statut": "Refus"})
    assert not ok and "routine" in message


def test_tableau_ouvert_dans_excel(tableau, monkeypatch):
    tableau.save()

    def refuse(*a, **k):
        raise PermissionError("ouvert")
    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", refuse)
    ok, message, _ = suivi_donnees.ajouter({"Entreprise": "A", "Statut": "Refus"})
    assert not ok and "Excel" in message


def test_formulaire_dans_la_page(client):
    h = client.get("/suivi").get_data(as_text=True)
    assert 'id="pli-ajouter"' in h and 'id="a-Entreprise"' in h and "ajouter()" in h
    assert "<option selected>Candidaté (autre canal)</option>" in h and "<option>Ajout manuel</option>" in h
