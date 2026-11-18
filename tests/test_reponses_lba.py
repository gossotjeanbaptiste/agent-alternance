"""Routine « Réponses La Bonne Alternance » (alternance/reponses_lba.py) : modèle et rédaction simulés."""
import pytest

import commun
import lmagent
import planification
import postuler
import reponses
import reponses_lba
from tableau import FORMULAIRE, LBA


@pytest.fixture
def redaction(monkeypatch):
    vu = {"lettres": [], "reponses": []}
    monkeypatch.setattr(postuler, "lettres_des_brouillons", lambda *a, **k: reponses.lettres())
    monkeypatch.setattr(postuler, "ecrire_lettre", lambda s, row: vu["lettres"].append(s.get(row, "Entreprise"))
                        or reponses.enregistrer_lettre(s.get(row, "Lien"), "Lettre"))

    def reponses_de(s, row, deja):
        if s.get(row, "Entreprise") == "Panne":
            raise ValueError("réponse du modèle illisible")
        vu["reponses"].append(s.get(row, "Entreprise"))
        reponses.enregistrer(s.get(row, "Lien"), {"motivations": "M"})
    monkeypatch.setattr(postuler, "reponses_de", reponses_de)
    return vu


def remplir(tableau, *lignes):
    for nom, statut, lien in lignes:
        tableau.add(**{"Entreprise": nom, "Statut": statut, "Lien": lien, "Poste": "Candidature spontanée"})
    tableau.save()


def test_complete_toutes_les_candidatures_lba(tableau, redaction, capsys):
    remplir(tableau, ("Sans Rien", LBA, "https://lba/1"), ("Sans Reponses", LBA, "https://lba/2"),
            ("Complete", LBA, "https://lba/3"), ("Site", FORMULAIRE, "https://site/c"), ("Mail", "Brouillon", ""))
    reponses.enregistrer_lettre("https://lba/2", "Déjà là")
    reponses.enregistrer("https://lba/3", {"lettre": "L", "motivations": "M"})
    assert reponses_lba.main() == 0
    assert redaction["lettres"] == ["Sans Rien"]                        # seulement les lettres absentes
    assert redaction["reponses"] == ["Sans Rien", "Sans Reponses"]      # spontanées comprises, pas le formulaire du site
    out = capsys.readouterr().out
    assert "3 candidature(s) à postuler sur La Bonne Alternance" in out and "2 à compléter" in out
    assert "2 candidature(s) complétée(s)" in out


def test_rien_a_faire(tableau, redaction, capsys):
    remplir(tableau, ("Complete", LBA, "https://lba/3"))
    reponses.enregistrer("https://lba/3", {"lettre": "L", "motivations": "M"})
    assert reponses_lba.main() == 0 and redaction["reponses"] == []
    assert "Rien à écrire" in capsys.readouterr().out


def test_une_erreur_n_arrete_pas_les_suivantes(tableau, redaction, capsys):
    remplir(tableau, ("Panne", LBA, "https://lba/p"), ("Suivante", LBA, "https://lba/s"))
    reponses.enregistrer_lettre("https://lba/p", "L")
    reponses.enregistrer_lettre("https://lba/s", "L")
    assert reponses_lba.main() == 0
    out = capsys.readouterr().out
    assert "⚠️ Panne : non écrit" in out and redaction["reponses"] == ["Suivante"] and "1 en échec" in out


def test_mode_essai_n_enregistre_rien(tableau, redaction):
    remplir(tableau, ("A", LBA, "https://lba/a"))
    reponses_lba.main(essai=True)
    assert commun.ESSAI is True and reponses.lire() == {}


def test_lancee_par_lmagent(monkeypatch):
    vu = {}
    monkeypatch.setattr(reponses_lba, "main", lambda essai=False: vu.update(essai=essai) or 0)
    assert lmagent.routine(["--routine", "reponses", "--essai"]) == 0 and vu == {"essai": True}


def test_dans_la_page_et_planifiable(client, monkeypatch):
    h = client.get("/routines").get_data(as_text=True)
    assert "lancer('reponses')" in h and "Réponses La Bonne Alternance" in h and 'id="heure-reponses"' in h
    monkeypatch.setattr(planification, "_schtasks", lambda *a: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    assert planification.planifier("reponses", "08:00")[0]


def test_routine_mails_recus(client, monkeypatch):
    """« Mails reçus » : bouton, planification, et lancement par lmagent (mode « mails » d'alternance.py)."""
    import sys
    import types
    vu = {}
    faux = types.ModuleType("alternance")
    faux.main = lambda mode: vu.update(mode=mode)
    monkeypatch.setitem(sys.modules, "alternance", faux)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    assert lmagent.routine(["--routine", "mails"]) == 0 and vu == {"mode": "mails"}
    h = client.get("/routines").get_data(as_text=True)
    assert "lancer('mails')" in h and "📩 Mails reçus" in h and 'id="heure-mails"' in h
    monkeypatch.setattr(planification, "_schtasks", lambda *a: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    assert planification.planifier("mails", "09:00")[0]


def test_bouton_lance_la_routine(client, monkeypatch):
    import routines
    lances = []
    monkeypatch.setattr(routines, "lancer", lambda nom, essai, fois, depuis=None: lances.append(nom))
    assert client.post("/api/routine/reponses", json={}).status_code == 200 and lances == ["reponses"]
