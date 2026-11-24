"""Mise à jour depuis le code (src/maj_code.py) : git pull en avance rapide, puis relance de l'interface."""
import pytest

import maj_code
import mise_a_jour


@pytest.fixture
def git(monkeypatch):
    """Faux git : réponses par commande (premier mot), commandes lancées notées."""
    vu = {"appels": [], "rep": {"rev-parse": (0, "main"), "fetch": (0, ""), "rev-list": (0, "3"),
                                "status": (0, ""), "pull": (0, "")}}
    monkeypatch.setattr(maj_code, "_git", lambda *a, **k: vu["appels"].append(a[0]) or vu["rep"][a[0]])
    return vu


def test_nouveautes_recuperees(git):
    assert maj_code.mettre_a_jour() == (True, "3 nouveauté(s) récupérée(s) (branche main) : l'interface redémarre.")
    assert git["appels"] == ["rev-parse", "fetch", "rev-list", "status", "pull"]


def test_deja_a_jour(git):
    git["rep"]["rev-list"] = (0, "0")
    relancer, message = maj_code.mettre_a_jour()
    assert not relancer and "à jour" in message and "pull" not in git["appels"]


def test_fichiers_modifies_rien_n_est_tire(git):
    git["rep"]["status"] = (0, " M web/app.py")
    relancer, message = maj_code.mettre_a_jour()
    assert not relancer and "modifiés" in message and "pull" not in git["appels"]


@pytest.mark.parametrize("cmd, mot", [("rev-parse", "impossible"), ("fetch", "fetch"), ("rev-list", "distante"),
                                      ("pull", "pull")])
def test_echecs(git, cmd, mot):
    git["rep"][cmd] = (1, "erreur")
    relancer, message = maj_code.mettre_a_jour()
    assert not relancer and mot in message


def test_sans_appliquer_rien_n_est_tire(git):
    relancer, message = maj_code.mettre_a_jour(appliquer=False)
    assert not relancer and "3 nouveauté" in message and "pull" not in git["appels"]


def test_verifier_depuis_le_code_relance(git, monkeypatch):
    monkeypatch.setattr(mise_a_jour.emplacements, "INSTALLEE", False)
    relances = []
    monkeypatch.setattr(maj_code, "lancer_relance", lambda: relances.append(1))
    lancee, _ = mise_a_jour.verifier(journal=lambda m: None)
    assert lancee and relances == [1]
    git["rep"]["rev-list"] = (0, "0")
    assert not mise_a_jour.verifier(journal=lambda m: None)[0] and relances == [1]


def test_commande_relance(monkeypatch):
    monkeypatch.setattr(maj_code.sys, "argv", [r"C:\Mes Projets\lm agent\lmagent.py"])
    script = maj_code.commande_relance(pid=4242)[-1]
    assert script.startswith("Wait-Process -Id 4242") and "$env:LMAGENT_SANS_NAVIGATEUR = '1'" in script
    assert "'\"" + r"C:\Mes Projets\lm agent\lmagent.py" + "\"'" in script and "-WindowStyle Hidden" in script


def test_bouton_refuse_pendant_une_routine(client, monkeypatch):
    import routines
    monkeypatch.setattr(mise_a_jour.emplacements, "INSTALLEE", False)
    monkeypatch.setattr(routines, "en_cours", lambda: True)
    monkeypatch.setattr(mise_a_jour, "verifier", lambda: pytest.fail("ne doit pas vérifier"))
    r = client.post("/api/mise_a_jour", json={}).get_json()
    assert not r["ok"] and "routine" in r["message"]
