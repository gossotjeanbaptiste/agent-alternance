"""Page LinkedIn : import de l'export (Connections.csv ou archive .zip) et ajout d'une relation (web/src/relations.py)."""
import io
import zipfile

import pytest

import relations

EXPORT = ("Notes:\n\"When exporting your connection data…\"\n\n"
          "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
          "Lou,Martin,https://www.linkedin.com/in/lou-martin,,Forgeval Dev,Développeuse,10 Nov 2026\n"
          "Marc,Durand,https://www.linkedin.com/in/marc-durand,,Comptanova,RH,12 Nov 2026\n")


@pytest.fixture(autouse=True)
def sans_fichier():
    for f in (relations.FICHIER, relations.FICHIER.with_name("Connections.csv.bak")):
        f.unlink(missing_ok=True)
    yield
    for f in (relations.FICHIER, relations.FICHIER.with_name("Connections.csv.bak")):
        f.unlink(missing_ok=True)


class Fichier:
    """Comme le FileStorage de werkzeug (fichier envoyé depuis la page)."""
    def __init__(self, nom, donnees):
        self.filename, self._b = nom, io.BytesIO(donnees)

    def read(self, n=-1):
        return self._b.read(n)


def archive(contenu, nom="Basic_LinkedInDataExport/Connections.csv"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(nom, contenu)
        z.writestr("Basic_LinkedInDataExport/Profile.csv", "First Name\nCamille\n")
    return b.getvalue()


def test_import_du_csv():
    ok, message = relations.importer(Fichier("Connections.csv", ("﻿" + EXPORT).encode("utf-8")))
    assert ok and "2 nouvelle(s)" in message
    assert [r["Company"] for r in relations.lire_relations()] == ["Forgeval Dev", "Comptanova"]


def test_import_de_l_archive_zip_sans_doublon():
    relations.importer(Fichier("Connections.csv", EXPORT.encode("utf-8")))
    plus = EXPORT + "Léa,Petit,https://www.linkedin.com/in/lea-petit,,Pixelo,Cheffe de projet,20 Nov 2026\n"
    ok, message = relations.importer(Fichier("export.zip", archive(plus)))
    assert ok and "3 relation(s) lue(s), 1 nouvelle(s)" in message
    assert len(relations.lire_relations()) == 3
    assert relations.FICHIER.with_name("Connections.csv.bak").exists()        # l'ancien fichier est gardé


@pytest.mark.parametrize("nom, donnees, attendu", [
    ("cv.pdf", b"%PDF", "Connections.csv ou l'archive"),
    ("export.zip", b"pas une archive", "illisible"),
    ("Connections.csv", b"Nom;Prenom\nx;y\n", "pas un export"),
])
def test_fichiers_refuses(nom, donnees, attendu):
    ok, message = relations.importer(Fichier(nom, donnees))
    assert not ok and attendu in message and not relations.FICHIER.exists()


def test_archive_sans_relations():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("Profile.csv", "x")
    ok, message = relations.importer(Fichier("export.zip", b.getvalue()))
    assert not ok and "Relations" in message


def test_fichier_trop_gros(monkeypatch):
    monkeypatch.setattr(relations, "TAILLE_MAX", 10)
    assert relations.importer(Fichier("Connections.csv", EXPORT.encode()))[0] is False


def test_ajout_a_la_main():
    ok, _ = relations.ajouter({"prenom": "Lou", "nom": "Martin", "entreprise": "Forgeval Dev",
                               "url": "https://www.linkedin.com/in/lou-martin"})
    assert ok and relations.lire_relations()[0]["Company"] == "Forgeval Dev"
    ok, message = relations.ajouter({"prenom": "Lou", "nom": "Martin", "entreprise": "Autre",
                                     "url": "https://www.linkedin.com/in/lou-martin/"})
    assert not ok and "déjà" in message                                       # même profil
    assert not relations.ajouter({"prenom": "X", "entreprise": ""})[0]
    assert not relations.ajouter({"prenom": "X", "entreprise": "Y", "url": "javascript:alert(1)"})[0]


def test_page_et_api(client, tableau):
    tableau.add(**{"Entreprise": "Forgeval Dev", "Statut": "Candidaté (mail)"})
    tableau.save()
    h = client.get("/linkedin").get_data(as_text=True)
    assert "Importer ton export LinkedIn" in h and "aucun export importé" in h
    r = client.post("/api/linkedin/importer", data={"fichier": (io.BytesIO(EXPORT.encode()), "Connections.csv")},
                    content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["ok"]
    h = client.get("/linkedin").get_data(as_text=True)
    assert "Lou Martin" in h and "parmi tes 2 relations" in h
    r = client.post("/api/linkedin/ajouter", json={"prenom": "Léa", "entreprise": "Pixelo"})
    assert r.get_json()["ok"] and len(relations.lire_relations()) == 3
    assert client.post("/api/linkedin/ajouter", json={"prenom": "Léa", "entreprise": "Pixelo"}).status_code == 400


def test_api_protegee(client):
    r = client.post("/api/linkedin/importer", jeton=False,
                    data={"fichier": (io.BytesIO(EXPORT.encode()), "Connections.csv")}, content_type="multipart/form-data")
    assert r.status_code == 403 and not relations.FICHIER.exists()
