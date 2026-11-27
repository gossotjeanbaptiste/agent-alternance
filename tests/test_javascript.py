"""Syntaxe JavaScript de toutes les pages : chaque script (fichiers de web/static et scripts écrits dans les
pages rendues) est vérifié par Node.js (node --check). Une seule erreur de syntaxe empêche tout le script de la
page de s'exécuter : en 1.1.1, un retour à la ligne dans une chaîne cassait le tri et les boutons « Envoyée » /
« Abandonner » de la page À postuler."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tableau import FORMULAIRE, LBA

STATIQUES = Path(__file__).resolve().parent.parent / "web" / "static"
EXTENSION = Path(__file__).resolve().parent.parent / "web" / "extension"
PAGES = ["/", "/suivi", "/postuler", "/ecartees", "/routines", "/linkedin", "/journal", "/parametres", "/assistant"]


@pytest.fixture
def node():
    n = shutil.which("node")
    if not n:
        pytest.skip("Node.js non installé")
    return n


def verifier(node, code, nom, tmp_path):
    f = tmp_path / (re.sub(r"\W", "_", nom) + ".js")
    f.write_text(code, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, f"{nom} : JavaScript invalide\n{r.stderr}"


@pytest.mark.parametrize("fichier", sorted(p.name for p in STATIQUES.glob("*.js")))
def test_fichiers_statiques(node, fichier, tmp_path):
    verifier(node, (STATIQUES / fichier).read_text(encoding="utf-8"), fichier, tmp_path)


@pytest.mark.parametrize("fichier", sorted(p.name for p in EXTENSION.glob("*.js")))
def test_extension_chrome(node, fichier, tmp_path):
    verifier(node, (EXTENSION / fichier).read_text(encoding="utf-8"), fichier, tmp_path)


@pytest.mark.parametrize("url", PAGES)
def test_scripts_des_pages(node, client, tableau, url, tmp_path):
    # des données pour que les pages affichent tous leurs éléments (cartes, menus de tri…)
    for nom, statut in (("Lba Co", LBA), ("Form Co", FORMULAIRE), ("Mail Co", "Brouillon"),
                        ("Sans Co", "Brouillon (adresse à trouver)")):
        tableau.add(**{"Entreprise": nom, "Statut": statut, "Email": "rh@mail.fr" if nom == "Mail Co" else ""})
    tableau.save()
    import refus
    refus.noter([{"Entreprise": n, "SIRET": s, "Code NAF": "47.41Z", "Activité": "Commerce", "Adresse": "Lyon",
                  "Recherche": "Lyon"} for n, s in (("A", "1"), ("B", "2"))])
    h = client.get(url).get_data(as_text=True)
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", h, re.S)
    assert scripts or url in ("/", "/suivi", "/linkedin", "/routines"), "aucun script trouvé"
    for i, code in enumerate(scripts):
        verifier(node, code, f"{url} script {i + 1}", tmp_path)
