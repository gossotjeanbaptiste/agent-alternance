"""Statuts et filtres des pages rangés par ordre alphabétique (accents et majuscules ignorés)."""
import re

import app
from tableau import STATUTS


def test_alphabetique_ignore_accents_et_majuscules():
    assert app.alphabetique(["Refus", "Abandonné", "À postuler", "brouillon", "Réponse"]) == \
        ["À postuler", "Abandonné", "brouillon", "Refus", "Réponse"]


def options(html, id_select):
    bloc = re.search(rf'<select id="{id_select}"[^>]*>(.*?)</select>', html, re.S).group(1)
    return [o for o in re.findall(r"<option[^>]*>([^<]*)</option>", bloc) if not o.startswith(("Tous", "Toutes"))]


def test_page_suivi(client, tableau):
    tableau.save()
    h = client.get("/suivi").get_data(as_text=True)
    for id_select in ("f-statut", "a-Statut"):
        assert options(h, id_select) == app.alphabetique(STATUTS)
    assert options(h, "f-source") == app.alphabetique(options(h, "f-source"))


def test_page_a_postuler():
    import emplacements
    h = (emplacements.RESSOURCES / "web" / "templates" / "postuler.html").read_text(encoding="utf-8")
    types = options(h, "f-type")
    assert len(types) == 4 and types == app.alphabetique(types)
