"""Pas de terminal qui clignote : CREATE_NO_WINDOW ajouté aux commandes d'un processus sans console."""
import subprocess
import sys

import pytest

import sans_fenetre as sf


def test_drapeau_ajoute_sans_console():
    assert sf.drapeaux(0, console=False) == sf.CREATE_NO_WINDOW
    assert sf.drapeaux(0x200, console=False) == 0x200 | sf.CREATE_NO_WINDOW   # autres drapeaux gardés


def test_rien_change_avec_console():
    assert sf.drapeaux(0, console=True) == 0


def test_fenetre_demandee_respectee():
    assert sf.drapeaux(sf.CREATE_NEW_CONSOLE, console=False) == sf.CREATE_NEW_CONSOLE
    assert sf.drapeaux(sf.DETACHED_PROCESS, console=False) == sf.DETACHED_PROCESS


@pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")
def test_activer_s_applique_aux_commandes(monkeypatch):
    vus = []
    monkeypatch.setattr(sf, "_ORIGINAL", lambda self, *a, creationflags=0, **k: vus.append(creationflags))
    monkeypatch.setattr(sf, "a_une_console", lambda: False)
    try:
        sf.activer()
        sf.activer()   # deux fois sans empiler
        subprocess.Popen.__init__(object.__new__(subprocess.Popen), ["tasklist"])
    finally:
        sf.desactiver()
    assert vus == [sf.CREATE_NO_WINDOW]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")
def test_commande_reelle_fonctionne():
    try:
        sf.activer()
        r = subprocess.run([sys.executable, "-c", "print('ok')"], capture_output=True, text=True, timeout=30)
    finally:
        sf.desactiver()
    assert r.stdout.strip() == "ok"
