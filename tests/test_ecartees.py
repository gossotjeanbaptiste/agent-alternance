"""Page « Écartées » (web/src/ecartees.py) : raison, site / recherche Google, candidater quand même, abandonner."""
import commun
import ecartees
import refus
import sources
from tableau import Suivi


def noter(*entreprises):
    refus.noter([{"Entreprise": nom, "SIRET": siret, "Code NAF": "47.41Z", "Activité": "Commerce de détail",
                  "Adresse": "12 rue X 69003 Lyon", "Site": site, "Recherche": "Lyon",
                  "Raison": "Activité hors informatique : Commerce de détail (47.41Z)"}
                 for nom, siret, site in entreprises])


def test_lecture_raison_site_et_recherche():
    noter(("Boutique", "1", "www.boutique.fr"), ("Sans Site", "2", ""))
    g = ecartees.lire()
    a = {l["Entreprise"]: l for l in g["a_examiner"]}
    assert a["Boutique"]["_raison"] == "Activité hors informatique : Commerce de détail (47.41Z)"
    assert a["Boutique"]["_site"] == "https://www.boutique.fr"                 # schéma ajouté
    assert a["Sans Site"]["_site"] == ""
    assert a["Sans Site"]["_recherche"] == "https://www.google.com/search?q=Sans+Site+Lyon"
    assert g["abandonnees"] == [] and g["demandees"] == []


def test_abandonner_puis_remettre():
    noter(("Boutique", "1", ""))
    assert ecartees.abandonner("1")[0]
    g = ecartees.lire()
    assert g["a_examiner"] == [] and [l["Entreprise"] for l in g["abandonnees"]] == ["Boutique"]
    assert ecartees.remettre("1")[0]
    assert [l["Entreprise"] for l in ecartees.lire()["a_examiner"]] == ["Boutique"]


def test_candidater_ajoute_a_la_feuille_a_contacter(tableau):
    noter(("Boutique", "12345678900011", "boutique.fr"))
    ok, msg = ecartees.candidater("12345678900011")
    assert ok and "À contacter" in msg
    s = Suivi(commun.chemin_tableau())
    o = sources.depuis_a_contacter(s)                  # reprise par la prochaine recherche, en premier
    assert len(o) == 1 and o[0]["entreprise"] == "Boutique" and o[0]["source"] == "Liste perso"
    assert o[0]["site"] == "https://boutique.fr" and o[0]["lieu"] == "12 rue X 69003 Lyon"
    assert "SIRET 12345678900011" in o[0]["infos"] and "Commerce de détail" in o[0]["infos"]
    g = ecartees.lire()
    assert g["a_examiner"] == [] and g["demandees"][0]["Décision"].startswith("Candidature demandée le ")


def test_candidater_deux_fois_refuse(tableau):
    noter(("Boutique", "1", ""))
    assert ecartees.candidater("1")[0]
    refus.decider("1", "")                              # remise dans la liste par erreur
    ok, msg = ecartees.candidater("1")
    assert not ok and "déjà dans la feuille" in msg


def test_candidater_deja_dans_le_suivi(tableau):
    tableau.add(**{"Entreprise": "Boutique", "Statut": "Brouillon"})
    tableau.wb.save(tableau.path)
    noter(("Boutique", "1", ""))
    ok, msg = ecartees.candidater("1")
    assert not ok and "déjà dans le tableau" in msg


def test_candidater_meme_nom_autre_adresse(tableau):
    """Un établissement du même nom, ailleurs, est déjà dans le tableau : la candidature est quand même possible."""
    tableau.add(**{"Entreprise": "Boutique", "Statut": "Brouillon", "Lieu": "1 rue Z 38000 Grenoble"})
    tableau.wb.save(tableau.path)
    noter(("Boutique", "12345678900011", ""))                          # adresse : 12 rue X 69003 Lyon
    ok, msg = ecartees.candidater("12345678900011")
    assert ok, msg
    o = sources.depuis_a_contacter(Suivi(commun.chemin_tableau()))[0]
    assert o["siret"] == "12345678900011"                               # SIRET repris pour la suite
    s = Suivi(commun.chemin_tableau())
    assert not __import__("tableau").deja_contactee(o, *s.deja_vus())   # la recherche ne l'ignorera pas


def test_deux_etablissements_ecartes_du_meme_nom(tableau):
    refus.noter([{"Entreprise": "Garage", "SIRET": s, "Code NAF": "45.20A", "Activité": "Garage", "Adresse": a,
                  "Recherche": "Lyon"} for s, a in (("11111111100011", "69003 Lyon"), ("22222222200022", "38000 Grenoble"))])
    assert len(ecartees.lire()["a_examiner"]) == 2
    assert ecartees.candidater("11111111100011")[0]
    assert ecartees.candidater("22222222200022")[0]                    # l'autre établissement aussi
    noms = [o["lieu"] for o in sources.depuis_a_contacter(Suivi(commun.chemin_tableau()))]
    assert noms == ["69003 Lyon", "38000 Grenoble"]


def test_meme_nom_meme_ville_refuse(tableau):
    tableau.add(**{"Entreprise": "Boutique", "Statut": "Brouillon", "Lieu": "69001 Lyon"})
    tableau.wb.save(tableau.path)
    noter(("Boutique", "1", ""))                                        # 12 rue X 69003 Lyon : même ville
    ok, msg = ecartees.candidater("1")
    assert not ok and "déjà dans le tableau" in msg


def test_candidater_ancien_tableau_sans_feuille(tableau):
    del tableau.wb["À contacter"]
    tableau.wb.save(tableau.path)
    noter(("Boutique", "1", ""))
    assert ecartees.candidater("1")[0]
    assert sources.depuis_a_contacter(Suivi(commun.chemin_tableau()))[0]["entreprise"] == "Boutique"


def test_candidater_pendant_une_routine(tableau, monkeypatch):
    monkeypatch.setattr(ecartees.routines, "en_cours", lambda: True)
    noter(("Boutique", "1", ""))
    ok, msg = ecartees.candidater("1")
    assert not ok and "routine" in msg


def test_candidater_tableau_ouvert_dans_excel(tableau, monkeypatch):
    noter(("Boutique", "1", ""))

    def refuse(*a, **k):
        raise PermissionError("ouvert")
    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", refuse)
    ok, msg = ecartees.candidater("1")
    assert not ok and "Excel" in msg
    assert ecartees.lire()["a_examiner"]                # décision non notée


def test_entreprise_inconnue():
    for action in ecartees.ACTIONS.values():
        assert not action("n'existe pas")[0]


# --- page et API -----------------------------------------------------------------------------------
def test_page(client):
    noter(("Boutique", "1", "boutique.fr"))
    h =client.get("/ecartees").get_data(as_text=True)
    assert "Boutique" in h and "Raison :" in h and "Commerce de détail (47.41Z)" in h
    assert 'href="https://boutique.fr"' in h and "google.com/search" in h
    assert "Candidater quand même" in h and "Abandonner" in h
    assert 'href="/ecartees"' in client.get("/").get_data(as_text=True)          # lien dans la barre


def test_page_vide(client):
    assert "Aucune entreprise écartée" in client.get("/ecartees").get_data(as_text=True)


def test_api(client, tableau):
    noter(("Boutique", "1", ""), ("Garage", "2", ""))
    r = client.post("/api/ecartee", json={"cle": "2", "action": "abandonner"})
    assert r.status_code == 200 and r.get_json()["ok"]
    assert client.post("/api/ecartee", json={"cle": "1", "action": "candidater"}).get_json()["ok"]
    h = client.get("/ecartees").get_data(as_text=True)
    assert 'id="pli-abandonnees"' in h and 'id="pli-demandees"' in h and "Remettre" in h
    assert client.post("/api/ecartee", json={"cle": "1", "action": "pirater"}).status_code == 400
    assert client.post("/api/ecartee", json={"cle": "inconnue", "action": "abandonner"}).status_code == 400


def test_api_protegee(anonyme):
    assert anonyme.post("/api/ecartee", json={"cle": "1", "action": "abandonner"}).status_code == 401
