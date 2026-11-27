"""Avancement en direct des routines (src/avancement.py) et routines programmées vues par la page Routines
(routines.externe / etat / annuler). Processus factices locaux : aucune vraie routine, aucun modèle."""
import subprocess
import sys
import time

import pytest

import avancement
import commun
import routines


@pytest.fixture(autouse=True)
def propre(monkeypatch):
    monkeypatch.delenv("LMAGENT_BOUCLE", raising=False)
    avancement.fichier().unlink(missing_ok=True)
    monkeypatch.setitem(routines.ROUTINE, "proc", None)
    routines._EXTERNE.update(quand=0, etat=None)
    yield
    avancement.fichier().unlink(missing_ok=True)


@pytest.fixture
def routine_programmee(tmp_path):
    """Un processus Python qui attend, comme une routine lancée par le Planificateur de tâches."""
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    yield p
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def test_etapes_notees():
    avancement.commencer("tout", 3)
    avancement.passage(2, 3)
    avancement.etape("Rédaction des candidatures", "Forgeval Dev", 2, 5)
    d = avancement.lire()
    assert d["routine"] == "tout" and d["passage"] == 2 and d["total"] == 3
    assert (d["etape"], d["detail"], d["k"], d["n"]) == ("Rédaction des candidatures", "Forgeval Dev", 2, 5)
    assert not d["fini"]
    avancement.finir(0)
    assert avancement.lire()["fini"] and avancement.lire()["etape"] == "Terminée"


def test_un_passage_de_boucle_ne_remet_pas_tout_a_zero(monkeypatch):
    avancement.commencer("tout", 3)
    avancement.passage(2, 3)
    monkeypatch.setenv("LMAGENT_BOUCLE", "123")
    avancement.commencer("tout")           # le passage lui-même (processus enfant)
    avancement.finir(0)                     # fin du passage : pas la fin de la routine
    d = avancement.lire()
    assert d["passage"] == 2 and d["total"] == 3 and not d["fini"]


def test_etape_de_la_routine_avec_ligne_au_journal(capsys):
    avancement.commencer("recherche")
    commun.etape("Rédaction des candidatures", "Pixelo", 1, 4, ligne="   ⏳ Rédaction pour Pixelo (1/4)…")
    assert "⏳ Rédaction pour Pixelo (1/4)…" in capsys.readouterr().out
    assert avancement.lire()["detail"] == "Pixelo"


def test_fichier_illisible_ou_absent():
    assert avancement.lire() == {} and avancement.en_cours() is None
    avancement.fichier().parent.mkdir(parents=True, exist_ok=True)
    avancement.fichier().write_text("{cassé", encoding="utf-8")
    assert avancement.lire() == {} and avancement.en_cours() is None


def test_en_cours_seulement_si_le_processus_tourne(routine_programmee):
    avancement.commencer("relances")
    d = avancement.lire()
    d["pid"], d["cree"] = routine_programmee.pid, avancement.creation(routine_programmee.pid)
    avancement._ecrire(d)
    assert avancement.en_cours()["routine"] == "relances"
    d["pid"] = 999999                       # processus disparu (routine arrêtée net)
    avancement._ecrire(d)
    assert avancement.en_cours() is None
    d["pid"], d["fini"] = routine_programmee.pid, True
    avancement._ecrire(d)
    assert avancement.en_cours() is None


def test_numero_repris_par_un_autre_programme(routine_programmee):
    """Routine arrêtée net (fichier « pas fini ») : un autre Python qui reçoit le même numéro n'est pas la routine."""
    vrai = avancement.creation(routine_programmee.pid)
    assert vrai is not None
    avancement._ecrire({"pid": routine_programmee.pid, "cree": vrai - 1, "routine": "tout", "fini": False})
    assert avancement.en_cours() is None
    assert not routines.en_cours() and routines.annuler()[0] is False      # rien n'est arrêté
    assert routine_programmee.poll() is None


def test_l_interface_ne_se_prend_pas_pour_la_routine():
    import os
    avancement._ecrire({"pid": os.getpid(), "cree": avancement.creation(os.getpid()), "routine": "tout", "fini": False})
    assert avancement.en_cours() is None


def test_routine_programmee_vue_et_annulable(routine_programmee, monkeypatch, tmp_path):
    monkeypatch.setattr(routines, "LOGS", tmp_path)
    journal = tmp_path / "web_20261127_090000_relances_planifiee.txt"
    journal.write_text("📬 Lecture de Outlook...\n", encoding="utf-8")
    avancement._ecrire({"pid": routine_programmee.pid, "cree": avancement.creation(routine_programmee.pid),
                        "routine": "relances", "passage": 1, "total": 1, "fini": False,
                        "etape": "Suivi des réponses", "detail": "Pixelo", "k": 3, "n": 40,
                        "debut": "2026-11-27T09:00:00", "sortie": str(journal)})
    assert routines.en_cours()                       # le tableau est protégé pendant une routine programmée
    e = routines.etat()
    assert e["en_cours"] and e["externe"] and e["nom"] == "Relances (programmée)" and e["debut"] == "09:00:00"
    assert e["avancement"]["detail"] == "Pixelo" and "Lecture de Outlook" in e["sortie"]
    dechargements = []
    monkeypatch.setattr(routines, "decharger_modele", lambda: dechargements.append(1))
    ok, _ = routines.annuler()
    assert ok
    routine_programmee.wait(timeout=15)
    for _ in range(50):
        if not routines.en_cours():
            break
        time.sleep(0.1)
    assert not routines.en_cours() and avancement.lire()["fini"]
    assert "annulée" in journal.read_text(encoding="utf-8")


def test_rien_en_cours():
    assert not routines.en_cours()
    ok, message = routines.annuler()
    assert not ok and "Aucune" in message


@pytest.mark.parametrize("nom, libelle", [
    ("web_20261126_134722_tout_x3.txt", "26/11 à 13:47 — Les deux ×3"),
    ("web_20261127_090000_relances_planifiee.txt", "27/11 à 09:00 — Relances (programmée)"),
    ("web_20261127_090000_recherche_x2_essai.txt", "27/11 à 09:00 — Recherche ×2 (essai)"),
    ("autre.txt", "autre.txt"),
])
def test_libelle_des_lancements(nom, libelle):
    assert routines.libelle_lancement(nom) == libelle


def test_page_routines(client):
    h = client.get("/routines").get_data(as_text=True)
    assert 'id="avancement"' in h and 'id="av-etape"' in h and 'id="pli-planification"' in h and "routines.js" in h
    assert client.get("/api/routine").get_json()["en_cours"] is False
