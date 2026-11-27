"""Tableau de suivi Excel, statuts, doublons (alternance/src/tableau/)."""
from datetime import date, datetime

import openpyxl
import pytest

import commun
import tableau
from tableau import Suivi


class TestNorm:
    @pytest.mark.parametrize("brut, attendu", [
        ("Lambert-Morel", "lambertmorel"),
        ("SARL Exemple Informatique", "exempleinformatique"),
        ("Groupe Ébène SAS", "ebene"),
        ("  Société   Démo  ", "societedemo"),
        (None, ""),
        (1234, "1234"),
    ])
    def test_norm(self, brut, attendu):
        assert tableau.norm(brut) == attendu


class TestAsDate:
    def test_types(self):
        assert tableau.as_date(datetime(2026, 11, 13, 10, 5)) == date(2026, 11, 13)
        assert tableau.as_date(date(2026, 11, 13)) == date(2026, 11, 13)
        assert tableau.as_date("2026-11-13 08:00:00") == date(2026, 11, 13)
        assert tableau.as_date("2026-11-13") == date(2026, 11, 13)

    @pytest.mark.parametrize("v", [None, "", "13/11/2026", "pas une date", 42])
    def test_invalide(self, v):
        assert tableau.as_date(v) is None


class TestDejaContactee:
    def setup_method(self):
        self.noms = {tableau.norm(n) for n in ("PIXELO", "Brio", "Lambert Morel")}
        self.domaines = {"exemple.fr"}
        self.sirets = {"12345678900011"}

    @pytest.mark.parametrize("o, attendu", [
        ({"entreprise": "Pixelo Lyon Est"}, True),          # nom contenu dans l'autre
        ({"entreprise": "BRIO"}, True),
        ({"entreprise": "Lambert-Morel"}, True),
        ({"entreprise": "Nouvelle Boîte"}, False),
        ({"entreprise": "Autre", "email": "rh@exemple.fr"}, True),   # même domaine
        ({"entreprise": "Autre", "email": "rh@ailleurs.fr"}, False),
        ({"entreprise": "Autre", "email": "rh@ailleurs.fr; jobs@exemple.fr"}, True),   # l'une des adresses
        ({"entreprise": "Autre", "siret": "12345678900011"}, True),
        ({"entreprise": "Autre", "siret": "99999999900099"}, False),
        ({"entreprise": ""}, True),                       # sans nom : ignorée
        ({"entreprise": "Abc"}, False),                   # nom court : pas de rapprochement partiel
    ])
    def test_cas(self, o, attendu):
        assert tableau.deja_contactee(o, self.noms, self.domaines, self.sirets) is attendu


class TestMemeNomAutreAdresse:
    """Plusieurs établissements du même nom : doublon seulement si même ville (ou ville inconnue)."""
    noms = {"pixelo": {"lyon"}, "brio": {"villeurbanne", "bron"}, "techvia": {""}}

    @pytest.mark.parametrize("o, attendu", [
        ({"entreprise": "PIXELO", "lieu": "12 rue X 69003 Lyon"}, True),            # même ville
        ({"entreprise": "PIXELO", "lieu": "5 avenue Y 38000 Grenoble"}, False),        # autre établissement
        ({"entreprise": "Pixelo Grenoble", "lieu": "38000 Grenoble"}, False),             # nom proche, autre ville
        ({"entreprise": "Pixelo Lyon Est", "lieu": "69800 Saint-Priest"}, False),
        ({"entreprise": "PIXELO"}, True),                                           # ville inconnue : prudence
        ({"entreprise": "Brio", "lieu": "Bron"}, True),
        ({"entreprise": "Brio", "lieu": "Vénissieux"}, False),
        ({"entreprise": "Techvia", "lieu": "Grenoble"}, True),                     # ville inconnue dans le tableau
        ({"entreprise": "PIXELO", "lieu": "Grenoble", "siret": "12345678900011"}, True),   # même SIRET
    ])
    def test_cas(self, o, attendu):
        assert tableau.deja_contactee(o, self.noms, set(), {"12345678900011"}) is attendu

    @pytest.mark.parametrize("lieu, cle", [
        ("12 rue X 69003 Lyon", "lyon"), ("12 RUE X 69003 LYON CEDEX 03", "lyon"), ("Lyon (69)", "lyon"),
        ("Saint-Étienne", "saintetienne"), ("rue X, Grenoble 38000", "grenoble"), ("", ""), (None, ""), ("69003", ""),
    ])
    def test_cle_lieu(self, lieu, cle):
        assert tableau.cle_lieu(lieu) == cle

    def test_tableau_avec_deux_etablissements(self, tableau):
        suivi = tableau          # (ici « tableau » est la fixture : le tableau de test)
        suivi.add(**{"Entreprise": "Pixelo", "Lieu": "69003 Lyon"})
        suivi.add(**{"Entreprise": "PIXELO", "Lieu": "38000 Grenoble"})
        noms, _, _ = suivi.deja_vus()
        assert noms == {"pixelo": {"lyon", "grenoble"}}
        import tableau as module
        assert not module.deja_contactee({"entreprise": "Pixelo", "lieu": "67000 Strasbourg"}, noms, set(), set())

    def test_retenir(self):
        noms = {}
        tableau.retenir(noms, {"entreprise": "Pixelo", "lieu": "38000 Grenoble"})
        assert noms == {"pixelo": {"grenoble"}}


class TestStatuts:
    def test_constantes_coherentes(self):
        for s in (tableau.LBA, tableau.FORMULAIRE, tableau.MAIL, *tableau.HORS_MAIL):
            assert s in tableau.STATUTS
        assert set(tableau.A_POSTULER) == {tableau.LBA, tableau.FORMULAIRE}

    def test_couleurs_valides(self):
        for statut, couleur in tableau.STATUTS.items():
            assert len(couleur) == 6 and int(couleur, 16) >= 0, statut

    @pytest.mark.parametrize("canal, attendu", [
        ("La Bonne Alternance", tableau.C_LBA), ("labonnealternance", tableau.C_LBA), ("LBA", tableau.C_LBA),
        ("linkedin", tableau.C_LINKEDIN), ("LinkedIn Easy Apply", tableau.C_LINKEDIN),
        ("formulaire du site", tableau.C_FORMULAIRE), ("form contact de x", tableau.C_FORMULAIRE),
        ("https://www.exemple.fr/contact", tableau.C_FORMULAIRE), ("site carrière", tableau.C_FORMULAIRE),
        ("mentor goal", tableau.C_AUTRE), ("", tableau.C_AUTRE), (None, tableau.C_AUTRE),
    ])
    def test_statut_par_canal(self, canal, attendu):
        assert tableau.statut_par_canal(canal) == attendu

    @pytest.mark.parametrize("statut, notes, source, attendu", [
        ("Envoyé", "", "", tableau.MAIL),
        ("Candidaté (hors mail)", "Candidature via : linkedin.", "", tableau.C_LINKEDIN),
        ("Candidaté (hors mail)", "Candidature via : labonnealternance.", "", tableau.C_LBA),
        ("Candidaté (hors mail)", "Candidature via : form contact de x.", "", tableau.C_FORMULAIRE),
        ("Candidaté (hors mail)", "SIRET 123", "La Bonne Alternance (Lyon)", tableau.C_LBA),
        ("Candidaté (hors mail)", "Importé", "Liste perso", tableau.C_AUTRE),
        ("Refus", "", "", "Refus"),
        (None, "", "", None),
    ])
    def test_ancien_statut(self, statut, notes, source, attendu):
        assert tableau.ancien_statut(statut, notes, source) == attendu


class TestSuivi:
    def test_creation_d_un_tableau_neuf(self, tableau):
        assert tableau.ws.title == "Suivi"
        assert [c.value for c in tableau.ws[1]] == tableau_cols()
        assert tableau.ac is not None
        assert list(tableau.rows()) == []

    def test_ajout_lecture_ecriture(self, tableau):
        tableau.add(**{"Entreprise": "Exemple", "Statut": "Brouillon", "Email": "rh@exemple.fr"})
        lignes = list(tableau.rows())
        assert len(lignes) == 1
        r = lignes[0]
        assert tableau.get(r, "Entreprise") == "Exemple"
        tableau.set(r, "Statut", tableau_mod().MAIL)
        assert tableau.get(r, "Statut") == tableau_mod().MAIL

    def test_save_relecture_et_mise_en_forme(self, tableau):
        tableau.add(**{"Entreprise": "A", "Statut": "Refus", "Date envoi": date(2026, 11, 2)})
        tableau.save()
        wb = openpyxl.load_workbook(tableau.path)
        assert "Statuts" in wb.sheetnames
        assert wb["Statuts"].sheet_state == "hidden"
        assert [r[0].value for r in wb["Statuts"].iter_rows()] == list(tableau_mod().STATUTS)
        dv = wb["Suivi"].data_validations.dataValidation
        assert len(dv) == 1 and dv[0].formula1.startswith("Statuts!")
        relu = Suivi(tableau.path)
        assert [relu.get(r, "Entreprise") for r in relu.rows()] == ["A"]

    def test_save_deux_fois_ne_duplique_pas_la_feuille_statuts(self, tableau):
        tableau.save()
        tableau.save()
        assert openpyxl.load_workbook(tableau.path).sheetnames.count("Statuts") == 1

    def test_save_en_mode_essai_n_ecrit_rien(self, tableau):
        commun.ESSAI = True
        tableau.add(**{"Entreprise": "A"})
        tableau.save()
        assert not tableau.path.exists()

    def test_tableau_verrouille_copie_datee(self, tableau, monkeypatch):
        tableau.add(**{"Entreprise": "A"})
        vrai_save = tableau.wb.save
        appels = []

        def save(chemin):
            appels.append(chemin)
            if len(appels) == 1:
                raise PermissionError("ouvert dans Excel")
            vrai_save(chemin)
        monkeypatch.setattr(tableau.wb, "save", save)
        tableau.save()
        assert len(appels) == 2 and appels[1] != tableau.path
        assert appels[1].name.startswith("suivi_") and appels[1].exists()

    def test_lignes_vides_ignorees(self, tableau):
        tableau.add(**{"Entreprise": "A"})
        tableau.ws.append([None] * len(tableau.h))
        tableau.add(**{"Entreprise": "B"})
        assert [tableau.get(r, "Entreprise") for r in tableau.rows()] == ["A", "B"]

    def test_colonnes_manquantes_ajoutees(self, tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suivi"
        ws.append(["Entreprise", "Statut"])
        ws.append(["Vieille", "Brouillon"])
        f = tmp_path / "ancien.xlsx"
        wb.save(f)
        s = Suivi(f)
        for col in tableau_cols():
            assert col in s.h
        r = next(s.rows())
        assert s.get(r, "Entreprise") == "Vieille" and s.get(r, "Notes") is None

    def test_migration_des_anciens_statuts(self, tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suivi"
        ws.append(tableau_cols())
        idx = {c: i for i, c in enumerate(tableau_cols())}

        def ligne(**v):
            l = [None] * len(idx)
            for k, x in v.items():
                l[idx[k]] = x
            ws.append(l)
        ligne(Entreprise="A", Statut="Envoyé")
        ligne(Entreprise="B", Statut="Candidaté (hors mail)", Notes="Candidature via : linkedin.")
        ligne(Entreprise="C", Statut="Candidaté (hors mail)", Source="La Bonne Alternance (Lyon)")
        f = tmp_path / "migration.xlsx"
        wb.save(f)
        s = Suivi(f)
        assert [s.get(r, "Statut") for r in s.rows()] == [tableau_mod().MAIL, tableau_mod().C_LINKEDIN,
                                                         tableau_mod().C_LBA]

    def test_deja_vus(self, tableau):
        tableau.add(**{"Entreprise": "Exemple SAS", "Email": "rh@exemple.fr", "Notes": "SIRET 12345678900011"})
        tableau.add(**{"Entreprise": "Perso", "Email": "jean@gmail.com",
                       "Lien": "https://labonnealternance/recruteurs_lba/98765432100022/x"})
        noms, domaines, sirets = tableau.deja_vus()
        assert noms == {"exemple": {""}, "perso": {""}}               # villes inconnues (pas de Lieu)
        assert domaines == {"exemple.fr"}            # gmail.com : messagerie grand public, ignorée
        assert sirets == {"12345678900011", "98765432100022"}


def tableau_cols():
    return list(tableau.COLS)


def tableau_mod():
    return tableau


def test_set_none_vide_la_case(tableau):
    """Régression : ws.cell(l, c, None) ne vidait pas la case (Relance prévue jamais effacée)."""
    tableau.add(**{"Entreprise": "A", "Relance prévue": "2026-11-20"})
    r = next(tableau.rows())
    tableau.set(r, "Relance prévue", None)
    assert tableau.get(r, "Relance prévue") is None
    tableau.save()
    relu = Suivi(tableau.path)
    assert relu.get(next(relu.rows()), "Relance prévue") is None
