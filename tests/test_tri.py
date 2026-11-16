"""Menu « Trier par » des pages À postuler et Écartées : attributs des cartes et logique de tri (web/static/tri.js,
exécutée avec Node.js s'il est installé)."""
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

import ecartees
import refus
from tableau import FORMULAIRE, LBA

TRI_JS = Path(__file__).resolve().parent.parent / "web" / "static" / "tri.js"


def ajouter(tableau, **vals):
    tableau.add(**vals)
    tableau.wb.save(tableau.path)


# --- logique de tri (Node.js) ------------------------------------------------------------------------
def trier(cartes, valeur, nombre=False):
    """Trie des cartes {attribut: valeur} avec tri.js ; renvoie les noms d'entreprise dans l'ordre obtenu."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js non installé")
    script = (f"const t = require({json.dumps(str(TRI_JS))});"
              f"const cartes = {json.dumps(cartes)}.map(d => ({{dataset: d}}));"
              f"console.log(JSON.stringify(t.trierCartes(cartes, {json.dumps(valeur)}, {json.dumps(nombre)})"
              ".map(c => c.dataset.entreprise)));")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


CARTES = [
    {"entreprise": "Zèbre", "date": "2026-11-10", "ville": "lyon", "type": "2", "passages": "3"},
    {"entreprise": "abeille", "date": "2026-11-15", "ville": "bron", "type": "0", "passages": "12"},
    {"entreprise": "Écureuil", "date": "", "ville": "", "type": "1", "passages": "1"},
    {"entreprise": "Martin", "date": "2026-11-12", "ville": "lyon", "type": "0", "passages": "2"},
]


@pytest.mark.parametrize("valeur, nombre, attendu", [
    ("entreprise:asc", False, ["abeille", "Écureuil", "Martin", "Zèbre"]),       # accents et majuscules ignorés
    ("entreprise:desc", False, ["Zèbre", "Martin", "Écureuil", "abeille"]),
    ("date:desc", False, ["abeille", "Martin", "Zèbre", "Écureuil"]),            # sans date : à la fin
    ("date:asc", False, ["Zèbre", "Martin", "abeille", "Écureuil"]),             # ... dans les deux sens
    ("ville:asc", False, ["abeille", "Martin", "Zèbre", "Écureuil"]),            # même ville : par nom
    ("type:asc", True, ["abeille", "Martin", "Écureuil", "Zèbre"]),
    ("passages:desc", True, ["abeille", "Zèbre", "Martin", "Écureuil"]),         # 12 avant 3 (nombres)
])
def test_tri(valeur, nombre, attendu):
    assert trier(CARTES, valeur, nombre) == attendu


def test_tri_inconnu_ne_casse_rien():
    assert sorted(trier(CARTES, "n_importe_quoi")) == sorted(c["entreprise"] for c in CARTES)


# --- page À postuler ---------------------------------------------------------------------------------
def test_page_a_postuler(client, tableau):
    ajouter(tableau, **{"Entreprise": "Lba Co", "Statut": LBA, "Lien": "https://lba/1", "Lieu": "12 rue X 69003 Lyon",
                        "Date ajout": date(2026, 11, 12)})
    ajouter(tableau, **{"Entreprise": "Form Co", "Statut": FORMULAIRE, "Lien": "https://f/1", "Lieu": "Bron"})
    ajouter(tableau, **{"Entreprise": "Mail Co", "Statut": "Brouillon", "Email": "rh@mailco.fr"})
    h = client.get("/postuler").get_data(as_text=True)
    assert '<select id="tri">' in h and 'activerTri("tri", "cartes", "tri-postuler")' in h and "tri.js" in h
    assert 'data-type="0" data-date="2026-11-12"' in h and 'data-ville="lyon"' in h
    assert 'data-type="1" data-date=""' in h and 'data-ville="bron"' in h
    assert 'data-type="2"' in h


def test_page_a_postuler_une_seule_carte_sans_menu(client, tableau):
    ajouter(tableau, **{"Entreprise": "Seule", "Statut": FORMULAIRE, "Lien": "https://f/1"})
    assert '<select id="tri">' not in client.get("/postuler").get_data(as_text=True)


# --- page Écartées -----------------------------------------------------------------------------------
def test_page_ecartees(client):
    refus.noter([{"Entreprise": n, "SIRET": s, "Code NAF": "47.41Z", "Activité": a, "Adresse": ad, "Recherche": "Lyon"}
                 for n, s, a, ad in (("Boutique", "1", "Commerce", "69003 Lyon"), ("Garage", "2", "Réparation", "Bron"))])
    h = client.get("/ecartees").get_data(as_text=True)
    assert '<select id="tri">' in h and 'activerTri("tri", "cartes", "tri-ecartees")' in h
    jour = f"{date.today():%Y-%m-%d}"
    assert f'data-activite="Commerce"' in h and 'data-ville="lyon"' in h
    assert f'data-derniere="{jour}" data-premiere="{jour}"' in h and 'data-passages="1"' in h


def test_page_ecartees_abandonnees_triees_aussi(client):
    """Une seule entreprise à examiner mais des abandonnées : le menu s'affiche et trie aussi les abandonnées."""
    refus.noter([{"Entreprise": n, "SIRET": s, "Code NAF": "47.41Z", "Activité": "Commerce", "Adresse": "Lyon",
                  "Recherche": "Lyon"} for n, s in (("A", "1"), ("B", "2"), ("C", "3"))])
    refus.decider("2", refus.ABANDONNEE)
    refus.decider("3", refus.ABANDONNEE)
    h = client.get("/ecartees").get_data(as_text=True)
    assert '<select id="tri">' in h and '<div id="cartes-abandonnees">' in h
    assert 'activerTri("tri", "cartes-abandonnees", "tri-ecartees")' in h


@pytest.mark.parametrize("jour, iso", [("13/11/2026", "2026-11-13"), ("1/2/2026", "2026-02-01"), ("", ""),
                                       ("pas une date", ""), (None, "")])
def test_iso(jour, iso):
    assert ecartees._iso(jour) == iso
