"""Description des réglages modifiables (alternance/src/reglages.py)."""
import json
from pathlib import Path

import pytest

import reglages

TYPES = {"entier", "decimal", "texte", "oui_non", "liste", "choix", "secret", "json"}


def test_chaque_reglage_est_complet():
    for r in reglages.REGLAGES:
        assert r["section"] and r["libelle"] and r["chemin"], r
        assert r["fichier"] in ("alternance", "agent"), r
        assert r["type"] in TYPES, r


def test_pas_de_doublon():
    cles = [(r["fichier"], r["chemin"]) for r in reglages.REGLAGES]
    assert len(cles) == len(set(cles))
    assert len(reglages.PAR_CHEMIN) == len(cles)


@pytest.mark.parametrize("r", reglages.REGLAGES, ids=lambda r: r["chemin"])
def test_valeur_par_defaut_du_bon_type(r):
    d, t = r["defaut"], r["type"]
    attendu = {"entier": int, "decimal": (int, float), "texte": str, "oui_non": bool, "liste": list,
               "choix": str, "secret": str, "json": (list, dict)}[t]
    assert isinstance(d, attendu), (r["chemin"], d)
    if t == "entier":
        assert not isinstance(d, bool)
    if t == "choix":
        assert d in r["choix"]


def test_reglages_tour_dans_la_config_agent():
    for r in reglages.REGLAGES:
        if r["tour"]:
            assert r["fichier"] == "agent" and r["chemin"].startswith("tour.")


def test_les_cles_de_la_config_d_exemple_sont_decrites():
    """Tout réglage de la config d'exemple (hors aides « _… » et rubriques gérées ailleurs) est éditable."""
    ex = json.loads((Path(reglages.__file__).parents[1] / "donnees" / "config_alternance.example.json")
                    .read_text(encoding="utf-8"))
    geres_ailleurs = {"signature_formulaire", "debut_signature", "ajouter_signature"}   # carte « Signature »

    def feuilles(d, prefixe=""):
        for k, v in d.items():
            if k.startswith("_"):
                continue
            chemin = f"{prefixe}{k}"
            if isinstance(v, dict) and chemin not in ("la_bonne_alternance.centre",):
                yield from feuilles(v, chemin + ".")
            else:
                yield chemin
    manquants = [c for c in feuilles(ex) if c.split(".")[0] not in geres_ailleurs
                 and ("alternance", c) not in reglages.PAR_CHEMIN]
    assert manquants == []


class TestChemins:
    def test_lire_chemin(self):
        d = {"a": {"b": {"c": 3}}, "x": 0}
        assert reglages.lire_chemin(d, "a.b.c") == 3
        assert reglages.lire_chemin(d, "x") == 0
        assert reglages.lire_chemin(d, "a.z", "défaut") == "défaut"
        assert reglages.lire_chemin(d, "x.y", 7) == 7
        assert reglages.lire_chemin({}, "a") is None

    def test_ecrire_chemin_cree_les_niveaux(self):
        d = {}
        reglages.ecrire_chemin(d, "a.b.c", 1)
        reglages.ecrire_chemin(d, "a.b.d", 2)
        reglages.ecrire_chemin(d, "e", 3)
        assert d == {"a": {"b": {"c": 1, "d": 2}}, "e": 3}


class TestValeur:
    def test_valeur_par_defaut_si_absente(self, cfg):
        cfg.pop("sites", None)
        assert reglages.valeur("sites.pages_max") == 6
        assert reglages.valeur("redaction.longueur_relance") == "60 à 110 mots"

    def test_valeur_de_la_config(self, cfg):
        cfg["sites"] = {"pages_max": 9}
        assert reglages.valeur("sites.pages_max") == 9
        cfg["mails_par_jour"] = 12
        assert reglages.valeur("mails_par_jour") == 12

    def test_questions_par_defaut(self):
        for cle, (titre, consigne) in reglages.QUESTIONS.items():
            assert reglages.valeur(f"redaction.questions.{cle}.titre") == titre
            assert reglages.valeur(f"redaction.questions.{cle}.consigne") == consigne

    def test_reglage_inconnu(self):
        with pytest.raises(KeyError):
            reglages.valeur("n.existe.pas")
