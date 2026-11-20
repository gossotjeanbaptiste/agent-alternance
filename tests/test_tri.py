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


# --- recherche et filtres (web/static/filtres.js) ------------------------------------------------------
FILTRES_JS = TRI_JS.with_name("filtres.js")


def filtrer(cartes, recherche, filtres):
    """Noms des cartes retenues par filtres.js (recherche + [{champ, valeur}])."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js non installé")
    script = (f"const f = require({json.dumps(str(FILTRES_JS))});"
              f"const cartes = {json.dumps(cartes)}.map(d => ({{dataset: d}}));"
              f"console.log(JSON.stringify(cartes.filter(c => f.carteCorrespond(c, {json.dumps(recherche)}, "
              f"{json.dumps(filtres)})).map(c => c.dataset.entreprise)));"
              f"console.log(JSON.stringify(f.valeursDistinctes(cartes, 'villenom')));")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    retenues, villes = r.stdout.strip().splitlines()
    return json.loads(retenues), json.loads(villes)


CARTES_F = [
    {"entreprise": "Pixelo", "texte": "Pixelo Technicien 69003 Lyon rh@pixelo.fr", "type": "2", "villenom": "Lyon", "source": "LinkedIn"},
    {"entreprise": "Écureuil", "texte": "Écureuil Développeur Bron", "type": "0", "villenom": "Bron", "source": "La Bonne Alternance"},
    {"entreprise": "Martin", "texte": "Martin Développeur web Lyon", "type": "1", "villenom": "Lyon", "source": "La Bonne Alternance"},
]


@pytest.mark.parametrize("recherche, filtres, attendu", [
    ("", [], ["Pixelo", "Écureuil", "Martin"]),
    ("ecureuil", [], ["Écureuil"]),                                     # sans accent, sans majuscule
    ("developpeur lyon", [], ["Martin"]),                               # tous les mots, dans n'importe quel ordre
    ("pixelo.fr", [], ["Pixelo"]),                                          # adresse mail
    ("", [{"champ": "villenom", "valeur": "Lyon"}], ["Pixelo", "Martin"]),
    ("", [{"champ": "type", "valeur": "0"}], ["Écureuil"]),
    ("developpeur", [{"champ": "source", "valeur": "La Bonne Alternance"}, {"champ": "villenom", "valeur": "Bron"}],
     ["Écureuil"]),
    ("", [{"champ": "villenom", "valeur": ""}], ["Pixelo", "Écureuil", "Martin"]),   # « Toutes les villes »
    ("introuvable", [], []),
])
def test_filtres(recherche, filtres, attendu):
    assert filtrer(CARTES_F, recherche, filtres)[0] == attendu


def test_valeurs_des_menus():
    assert filtrer(CARTES_F, "", [])[1] == ["Bron", "Lyon"]            # distinctes et triées


def test_barre_de_filtres_sur_les_pages(client, tableau):
    ajouter(tableau, **{"Entreprise": "Lba Co", "Statut": LBA, "Lien": "https://lba/1", "Lieu": "12 RUE X 69003 LYON",
                        "Source": "La Bonne Alternance (Lyon)", "Poste": "Candidature spontanée"})
    ajouter(tableau, **{"Entreprise": "Mail Co", "Statut": "Brouillon", "Email": "rh@mailco.fr", "Source": "LinkedIn"})
    h = client.get("/postuler").get_data(as_text=True)
    for id_ in ('id="recherche"', 'id="f-type"', 'id="f-source"', 'id="f-ville"', 'id="compte"', 'id="aucun"', "filtres.js"):
        assert id_ in h, id_
    assert 'data-villenom="Lyon" data-source="La Bonne Alternance"' in h          # source sans la ville de recherche
    assert 'data-texte="Lba Co Candidature spontanée 12 RUE X 69003 LYON' in h
    refus.noter([{"Entreprise": n, "SIRET": s, "Code NAF": "47.41Z", "Activité": "Commerce", "Adresse": "38000 GRENOBLE",
                  "Recherche": "Lyon"} for n, s in (("A", "1"), ("B", "2"))])
    e = client.get("/ecartees").get_data(as_text=True)
    for id_ in ('id="recherche"', 'id="f-activite"', 'id="f-ville"', 'id="compte"', "filtres.js"):
        assert id_ in e, id_
    assert 'data-villenom="Grenoble"' in e and "47.41Z" in e


@pytest.mark.parametrize("jour, iso", [("13/11/2026", "2026-11-13"), ("1/2/2026", "2026-02-01"), ("", ""),
                                       ("pas une date", ""), (None, "")])
def test_iso(jour, iso):
    assert ecartees._iso(jour) == iso


# --- recherche et filtres retenus d'un rechargement à l'autre, bouton Recharger ---------------------------
def retenir(gardes, menus):
    """Valeurs des champs après retenirChamps (faux document et faux localStorage), puis ce qui est gardé
    après une saisie dans la recherche."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js non installé")
    script = (
        "const stock = {'filtres-x': " + json.dumps(json.dumps(gardes)) + "};"
        "global.localStorage = {getItem: k => stock[k] || null, setItem: (k, v) => { stock[k] = v; }};"
        "const els = {};"
        "for (const [id, options] of Object.entries(" + json.dumps(menus) + ")) {"
        "  els[id] = {id, value: '', tagName: options ? 'SELECT' : 'INPUT', options: (options || []).map(v => ({value: v})),"
        "             ecouteurs: [], addEventListener(t, f) { this.ecouteurs.push(f); }};"
        "}"
        "global.document = {getElementById: id => els[id] || null};"
        f"const f = require({json.dumps(str(FILTRES_JS))});"
        "f.retenirChamps(Object.keys(els), 'filtres-x');"
        "console.log(JSON.stringify(Object.fromEntries(Object.values(els).map(e => [e.id, e.value]))));"
        "els.recherche.value = 'pixelo'; els.recherche.ecouteurs.forEach(g => g());"
        "console.log(stock['filtres-x']);")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    valeurs, garde = r.stdout.strip().splitlines()
    return json.loads(valeurs), json.loads(garde)


def test_filtres_remis_apres_rechargement():
    valeurs, garde = retenir({"recherche": "lyon", "f-type": "3", "f-ville": "Annecy"},
                             {"recherche": None, "f-type": ["", "0", "3"], "f-ville": ["", "Lyon"]})
    assert valeurs == {"recherche": "lyon", "f-type": "3", "f-ville": ""}   # ville disparue de la page : ignorée
    assert garde["recherche"] == "pixelo" and garde["f-type"] == "3"


def test_memoire_illisible_sans_planter():
    valeurs, _ = retenir("pas un objet", {"recherche": None})
    assert valeurs == {"recherche": ""}


@pytest.fixture
def sans_outlook(monkeypatch):
    import lettres
    monkeypatch.setattr(lettres, "_outlook_ferme", lambda: True)
    monkeypatch.setitem(lettres.CACHE, "quand", 0)


def test_boutons_recharger_et_memoire_sur_les_trois_pages(client, tableau, sans_outlook):
    ajouter(tableau, **{"Entreprise": "Lba Co", "Statut": LBA, "Lieu": "69003 Lyon"})
    ajouter(tableau, **{"Entreprise": "Mail Co", "Statut": "Brouillon", "Email": "rh@mailco.fr"})
    refus.noter([{"Entreprise": n, "SIRET": s, "Activité": "Commerce", "Adresse": "38000 GRENOBLE"}
                 for n, s in (("A", "1"), ("B", "2"))])
    for page, cle in (("/suivi", "filtres-suivi"), ("/postuler", "filtres-postuler"), ("/ecartees", "filtres-ecartees")):
        h = client.get(page).get_data(as_text=True)
        assert 'onclick="recharger()"' in h and "Effacer les filtres" in h and cle in h, page


def test_recharger_relit_les_lettres(client, tableau, sans_outlook):
    import lettres
    lettres.CACHE["quand"] = 10 ** 12          # cache « tout frais » : pas relu sans le bouton
    client.get("/postuler")
    assert lettres.CACHE["quand"] == 10 ** 12
    client.get("/postuler?frais=1")
    assert lettres.CACHE["quand"] != 10 ** 12
