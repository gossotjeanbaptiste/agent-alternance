"""Fiche d'une entreprise modifiée depuis la page Suivi (web/src/fiche.py, /api/suivi/fiche)."""
from tableau import Suivi


def preparer(client, tableau):
    tableau.save()
    client.post("/api/suivi/ajouter", json={"Entreprise": "Pixelmont", "Lieu": "Lyon", "Statut": "Candidaté (autre canal)"})
    s = Suivi(tableau.path)
    return next(r[0].row for r in s.rows() if s.get(r, "Entreprise") == "Pixelmont")


def ligne(tableau, nom):
    s = Suivi(tableau.path)
    return next({c: s.get(r, c) for c in s.h} for r in s.rows() if s.get(r, "Entreprise") == nom)


def test_adresse_et_contacts_modifies(client, tableau):
    n = preparer(client, tableau)
    r = client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Pixelmont", "champs": {
        "Lieu": "12 rue de la République, 69002 Lyon", "Contact": "Camille Durand (RH)", "Email": "rh@pixelmont.fr",
        "Téléphone": "04 00 00 00 00", "Notes": "Tutrice : Lou Martin"}})
    assert r.status_code == 200 and r.get_json()["ok"]
    l = ligne(tableau, "Pixelmont")
    assert l["Lieu"] == "12 rue de la République, 69002 Lyon" and l["Contact"] == "Camille Durand (RH)"
    assert l["Email"] == "rh@pixelmont.fr" and l["Notes"] == "Tutrice : Lou Martin"
    assert l["Statut"] == "Candidaté (autre canal)"            # le reste de la ligne n'est pas touché


def test_plusieurs_adresses(client, tableau):
    n = preparer(client, tableau)
    r = client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Pixelmont",
                                              "champs": {"Email": " RH@pixelmont.fr , jobs@pixelmont.fr;rh@pixelmont.fr "}})
    assert r.get_json()["ok"]
    assert ligne(tableau, "Pixelmont")["Email"] == "rh@pixelmont.fr; jobs@pixelmont.fr"   # rangées, sans doublon
    assert client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Pixelmont",
                                                 "champs": {"Email": ""}}).get_json()["ok"]
    assert not ligne(tableau, "Pixelmont")["Email"]                                          # vidée


def test_entreprise_renommee(client, tableau):
    n = preparer(client, tableau)
    assert client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Pixelmont",
                                                 "champs": {"Entreprise": "Pixelmont SAS"}}).get_json()["ok"]
    assert ligne(tableau, "Pixelmont SAS")["Lieu"] == "Lyon"


def test_refus(client, tableau):
    n = preparer(client, tableau)
    for champs in ({"Email": "rh@pixelmont.fr; pas-une-adresse"}, {"Entreprise": "  "}, {"Lien": "javascript:alert(1)"}, {}):
        r = client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Pixelmont", "champs": champs})
        assert r.status_code == 400 and not r.get_json()["ok"]
    r = client.post("/api/suivi/fiche", json={"ligne": n, "entreprise": "Autre", "champs": {"Lieu": "Grenoble"}})
    assert not r.get_json()["ok"] and "introuvable" in r.get_json()["message"]
    assert client.post("/api/suivi/fiche", json={"ligne": "x", "entreprise": "Pixelmont"}).status_code == 400
    assert ligne(tableau, "Pixelmont")["Lieu"] == "Lyon"


def test_bouton_et_formulaire_dans_la_page(client, tableau):
    preparer(client, tableau)
    h = client.get("/suivi").get_data(as_text=True)
    assert 'id="fiche"' in h and "ouvrirFiche(this)" in h and "enregistrerFiche()" in h
    assert "data-fiche='{&#34;_0&#34;: &#34;Pixelmont&#34;" in h or '"_0": "Pixelmont"' in h
