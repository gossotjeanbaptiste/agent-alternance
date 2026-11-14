"""Sources d'entreprises (alternance/src/sources.py) et liste des entreprises écartées (refus.py).
L'API La Bonne Alternance est simulée."""
import csv
import io
import json
from datetime import date, datetime

import pytest

import commun
import refus
import sources


# --- poids des villes ---------------------------------------------------------------------------
LYON = {"nom": "Lyon", "lat": 45.764, "lon": 4.8357}
VILLEURBANNE = {"nom": "Villeurbanne", "lat": 45.7719, "lon": 4.8902}
ST_ETIENNE = {"nom": "Saint-Étienne", "lat": 45.4397, "lon": 4.3872}
GRENOBLE = {"nom": "Grenoble", "lat": 45.1885, "lon": 5.7245}


def test_distance():
    assert sources._distance_km(LYON, LYON) == 0
    assert 48 <= sources._distance_km(LYON, ST_ETIENNE) <= 52
    assert 3.5 <= sources._distance_km(LYON, VILLEURBANNE) <= 5
    assert sources._distance_km(LYON, GRENOBLE) == pytest.approx(sources._distance_km(GRENOBLE, LYON))


def test_poids_villes():
    c = {"centre": LYON, "villes_prioritaires": ["saint-etienne"], "demi_distance_km": 30, "poids_min": 0.05,
         "villes": [LYON, VILLEURBANNE, ST_ETIENNE, GRENOBLE, {"nom": "Manuelle", "lat": 0, "lon": 0, "poids": 0.7}]}
    p = sources.poids_villes(c)
    assert p["Lyon"] == 1.0
    assert p["Saint-Étienne"] == 1.0              # prioritaire (comparaison sans accents ni majuscules)
    assert 0.85 < p["Villeurbanne"] < 1.0          # tout près
    assert 0.1 < p["Grenoble"] < 0.2               # ~95 km : environ 1/8
    assert p["Manuelle"] == 0.7                    # poids écrit à la main


def test_poids_minimum_et_sans_centre():
    loin = {"nom": "Loin", "lat": 48.85, "lon": 2.35}
    assert sources.poids_villes({"centre": LYON, "villes": [loin], "poids_min": 0.05})["Loin"] == 0.05
    assert sources.poids_villes({"villes": [loin]})["Loin"] == 1.0


def test_ordre_pondere_favorise_les_villes_lourdes():
    c = {"centre": LYON, "villes": [LYON, GRENOBLE], "demi_distance_km": 10, "poids_min": 0.01}
    premiers = [sources.ordre_pondere(c)[0]["nom"] for _ in range(300)]
    assert premiers.count("Lyon") > 250
    assert sorted(v["nom"] for v in sources.ordre_pondere(c)) == ["Grenoble", "Lyon"]


@pytest.mark.parametrize("code, attendu", [
    ("62.01Z", True), ("58.29C", True), ("26.20Z", True), ("46.51Z", True), ("61.10Z", True),
    ("47.41Z", False), ("95.11Z", False), ("38.21Z", False), ("46.66Z", False),
    ("", True), (None, True),        # activité inconnue : on garde
])
def test_activite_acceptee(code, attendu):
    assert sources.activite_acceptee(code, {}) is attendu


def test_activite_acceptee_liste_personnalisee():
    assert sources.activite_acceptee("95.11Z", {"naf_acceptes": ["95.11"]}) is True
    assert sources.activite_acceptee("62.01Z", {"naf_acceptes": ["95.11"]}) is False


# --- La Bonne Alternance (API simulée) -------------------------------------------------------------
def recruteur(nom, naf="62.01Z", label="Programmation informatique", recipient=True, site="", siret="11111111100011"):
    return {"workplace": {"name": nom, "siret": siret, "website": site, "size": "10-19",
                          "domain": {"naf": {"code": naf, "label": label}},
                          "location": {"address": "1 rue X 69003 Lyon"}, "description": "Éditeur de logiciels"},
            "apply": {"url": f"https://labonnealternance.example/{nom}", "phone": "0400000000",
                      "recipient_id": "partners_1" if recipient else None}}


@pytest.fixture
def api(monkeypatch, cfg):
    cfg["la_bonne_alternance"].update({"actif": True, "jeton_api": "jeton", "villes": [LYON], "centre": LYON})
    reponses = {"jobs": [], "recruiters": []}
    demandes = []

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        demandes.append(req)
        return R(json.dumps(reponses).encode())
    monkeypatch.setattr(sources.urllib.request, "urlopen", urlopen)
    api.reponses, api.demandes = reponses, demandes
    return api


class TestDepuisLba:
    def test_inactif_ou_sans_jeton(self, cfg, capsys):
        cfg["la_bonne_alternance"]["actif"] = False
        assert list(sources.depuis_lba() or []) == []
        cfg["la_bonne_alternance"].update({"actif": True, "jeton_api": ""})
        assert list(sources.depuis_lba() or []) == []

    def test_requete(self, api):
        list(sources.depuis_lba())
        req = api.demandes[0]
        assert req.full_url.startswith("https://api.apprentissage.beta.gouv.fr/api/job/v1/search?")
        assert "latitude=45.764" in req.full_url and "radius=" in req.full_url
        assert req.get_header("Authorization") == "Bearer jeton"

    def test_entreprise_postulable_ou_non(self, api):
        api.reponses["recruiters"] = [recruteur("AVEC BOUTON"), recruteur("Sans Bouton", recipient=False, siret="2")]
        o = {x["entreprise"]: x for x in sources.depuis_lba()}
        assert o["Avec Bouton"]["lba_postulable"] is True          # nom en majuscules remis en forme
        assert o["Sans Bouton"]["lba_postulable"] is False
        x = o["Avec Bouton"]
        assert x["poste"] == "Candidature spontanée" and x["siret"] == "11111111100011"
        assert x["source"] == "La Bonne Alternance (Lyon)" and x["telephone"] == "0400000000"
        assert "Activité : Programmation informatique" in x["infos"]
        assert "salariés" not in x["infos"] and "Taille" not in x["infos"]   # volontairement absente

    def test_filtre_d_activite_et_liste_des_refus(self, api):
        api.reponses["recruiters"] = [recruteur("Info"),
                                      recruteur("Boutique", naf="47.41Z", label="Commerce de détail", siret="3"),
                                      recruteur("Déchets", naf="38.21Z", label="Traitement des déchets", siret="4")]
        noms = [x["entreprise"] for x in sources.depuis_lba()]
        assert noms == ["Info"]
        notes = refus.lire()
        assert set(notes) == {"3", "4"}
        assert notes["3"]["Code NAF"] == "47.41Z" and notes["3"]["Recherche"] == "Lyon"
        assert notes["3"]["Raison"] == "Activité hors informatique : Commerce de détail (47.41Z)"
        assert notes["3"]["Décision"] == ""

    def test_vraies_offres_jamais_filtrees(self, api):
        offre = recruteur("Magasin", naf="47.41Z", label="Commerce de détail")
        offre["offer"] = {"title": "Développeur web en alternance", "description": "Offre"}
        api.reponses["jobs"] = [offre]
        o = list(sources.depuis_lba())
        assert [x["poste"] for x in o] == ["Développeur web en alternance"]
        assert o[0]["lba_postulable"] is True

    def test_sans_nom_ignore(self, api):
        r = recruteur("x")
        r["workplace"]["name"] = None
        api.reponses["recruiters"] = [r]
        assert list(sources.depuis_lba()) == []

    def test_erreur_api_ville_suivante(self, monkeypatch, cfg):
        cfg["la_bonne_alternance"].update({"actif": True, "jeton_api": "j", "villes": [LYON, GRENOBLE]})
        monkeypatch.setattr(sources.urllib.request, "urlopen",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("panne")))
        assert list(sources.depuis_lba()) == []


class TestDepuisLinkedin:
    def test_offres_extraites(self, cfg, faux_modele, messagerie):
        cfg["alertes_linkedin"] = {"actif": True, "expediteurs": ["jobalerts-noreply@linkedin.com"], "jours": 3}
        recus = [{"de": "jobalerts-noreply@linkedin.com", "corps": "offres…", "date": datetime(2026, 11, 10)},
                 {"de": "ami@exemple.fr", "corps": "salut", "date": datetime(2026, 11, 10)}]
        faux_modele.reponses_json = [[{"entreprise": "Boîte", "poste": "Dev", "lieu": "Lyon"}, {"entreprise": ""}]]
        o = sources.depuis_linkedin(messagerie(recus=recus))
        assert len(o) == 1 and o[0]["entreprise"] == "Boîte" and o[0]["source"] == "LinkedIn"
        assert o[0]["lien"] == "Alerte LinkedIn du 10/11"
        assert len(faux_modele.consignes) == 1

    def test_inactif(self, cfg, messagerie):
        cfg["alertes_linkedin"] = {"actif": False}
        assert sources.depuis_linkedin(messagerie()) == []

    def test_alerte_illisible(self, cfg, faux_modele, messagerie):
        cfg["alertes_linkedin"] = {"actif": True, "expediteurs": ["linkedin"], "jours": 3}
        faux_modele.reponses_json = [ValueError("pas du json")]
        recus = [{"de": "x@linkedin.com", "corps": "?", "date": datetime(2026, 11, 10)}]
        assert sources.depuis_linkedin(messagerie(recus=recus)) == []


class TestAContacter:
    def test_lignes_non_traitees(self, tableau):
        tableau.ac.append(["Boîte A", "Dev", "Lyon", "Jean", " jean@a.fr ", "https://a.fr", "Super", None])
        tableau.ac.append(["Boîte B", "", "", "", "", "", "", "oui"])
        o = sources.depuis_a_contacter(tableau)
        assert [x["entreprise"] for x in o] == ["Boîte A"]
        assert o[0]["email"] == "jean@a.fr" and o[0]["source"] == "Liste perso"
        assert o[0]["_ligne"][1] == 2

    def test_sans_feuille(self, tableau):
        tableau.ac = None
        assert sources.depuis_a_contacter(tableau) == []


# --- liste des refus -------------------------------------------------------------------------------
class TestRefus:
    def e(self, nom="Boutique", siret="1"):
        return {"Entreprise": nom, "SIRET": siret, "Code NAF": "47.41Z", "Activité": "Commerce", "Adresse": "",
                "Recherche": "Lyon"}

    def test_noter_et_relire(self):
        refus.noter([self.e()])
        l = refus.lire()["1"]
        assert l["Passages"] == "1" and l["Première fois"] == f"{date.today():%d/%m/%Y}"

    def test_compte_une_fois_par_jour(self):
        refus.noter([self.e()])
        refus.noter([self.e()])
        assert refus.lire()["1"]["Passages"] == "1"

    def test_jour_suivant_incremente(self):
        refus.noter([self.e()])
        tout = refus.lire()
        tout["1"]["Dernière fois"] = "01/01/2026"
        with open(refus.FICHIER, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=refus.COLS, delimiter=";")
            w.writeheader()
            w.writerows(tout.values())
        refus.noter([self.e()])
        l = refus.lire()["1"]
        assert l["Passages"] == "2" and l["Première fois"] == f"{date.today():%d/%m/%Y}"

    def test_sans_siret_cle_par_nom(self):
        refus.noter([self.e(siret="")])
        assert "Boutique" in refus.lire()

    def test_mode_essai_n_ecrit_rien(self):
        commun.ESSAI = True
        refus.noter([self.e()])
        assert not refus.FICHIER.exists()

    def test_liste_vide(self):
        refus.noter([])
        assert not refus.FICHIER.exists()

    def test_fichier_ouvert_dans_excel(self, monkeypatch, capsys):
        import builtins
        vrai_open = builtins.open

        def ouvre(f, mode="r", *a, **k):
            if "w" in mode and str(f) == str(refus.FICHIER):
                raise PermissionError("ouvert")
            return vrai_open(f, mode, *a, **k)
        monkeypatch.setattr(builtins, "open", ouvre)
        refus.noter([self.e()])
        assert "ouvert" in capsys.readouterr().out

    def test_raison_notee_ou_deduite(self):
        assert refus.raison({"Raison": "Trop loin"}) == "Trop loin"
        assert refus.raison({"Activité": "Commerce", "Code NAF": "47.41Z"}) == "Activité hors informatique : Commerce (47.41Z)"
        assert refus.raison({}) == "Activité hors informatique : inconnue"

    def test_decision_gardee_quand_elle_revient(self):
        refus.noter([self.e()])
        assert refus.decider("1", refus.ABANDONNEE) == (True, "Enregistré.")
        tout = refus.lire()
        tout["1"]["Dernière fois"] = "01/01/2026"
        refus.ecrire(tout)
        refus.noter([self.e()])
        l = refus.lire()["1"]
        assert l["Décision"] == refus.ABANDONNEE and l["Passages"] == "2"

    def test_decider_entreprise_inconnue(self):
        ok, msg = refus.decider("rien", refus.ABANDONNEE)
        assert not ok and "introuvable" in msg

    def test_ancien_fichier_sans_nouvelles_colonnes(self):
        refus.FICHIER.write_text("Entreprise;SIRET;Code NAF;Activité;Adresse;Recherche;Première fois;Dernière fois;"
                                 "Passages\nBoutique;1;47.41Z;Commerce;;Lyon;01/01/2026;01/01/2026;3\n", encoding="utf-8-sig")
        l = refus.lire()["1"]
        assert l["Décision"] == "" and l["Site"] == "" and l["Passages"] == "3"
        assert refus.decider("1", refus.ABANDONNEE)[0]
        assert refus.lire()["1"]["Passages"] == "3"

    def test_format_excel(self):
        refus.noter([self.e("Z"), self.e("A", "2")])
        brut = refus.FICHIER.read_bytes()
        assert brut.startswith(b"\xef\xbb\xbf")                 # BOM : accents corrects dans Excel
        assert brut.splitlines()[0].decode("utf-8-sig").split(";") == refus.COLS
