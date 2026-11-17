"""Messages de diagnostic du démarrage de LM Studio sur la tour (src/tour.py, branche main).
Aucune connexion à la tour : SSH (ps_distant) et l'état du serveur sont simulés."""
import subprocess
import types

import pytest

tour = pytest.importorskip("tour")      # branche local-simple : pas de tour

CLIXML = ('#< CLIXML\r\n<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
          '<Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T></TN></Obj>'
          '</Objs>')


def resultat(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


class TestErreurPowershell:
    def test_progression_seule_n_est_pas_une_erreur(self):
        """Le bruit « #< CLIXML » (barre de progression) n'est plus montré comme une erreur."""
        assert "CLIXML" not in tour.erreur_powershell(resultat(stderr=CLIXML, code=1))
        assert "code 1" in tour.erreur_powershell(resultat(stderr=CLIXML, code=1))

    def test_vraie_erreur_extraite(self):
        err = CLIXML.replace("</Objs>", '<S S="Error">Accès refusé._x000D__x000A_</S></Objs>')
        assert tour.erreur_powershell(resultat(stderr=err, code=1)) == "Accès refusé."

    def test_sans_reponse(self):
        assert "pas de réponse SSH" in tour.erreur_powershell(None)


@pytest.mark.parametrize("sortie, attendu", [
    (None, "ne répond plus en SSH"),
    ("SESSION=\nLMS=True\nBIONIC=False\nTACHE=0", "aucune session Windows"),
    ("SESSION=TOUR\\moi\nLMS=False\nBIONIC=False\nTACHE=0", "lms.exe introuvable"),
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=True\nTACHE=0", "serveur ne répond pas sur le port"),
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=False\nTACHE=2147942402", "a échoué (code 2147942402)"),
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=False\nTACHE=267009", "ne s'est pas lancé"),
    # le cas réel : mise à jour de LM Studio interrompue, l'installeur attend dans lm-studio-updater\pending
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=False\nTACHE=1\nAPPLI=False\n"
     "EN_ATTENTE=C:\\Users\\moi\\AppData\\Local\\lm-studio-updater\\pending\\Bionic-1.2.1-win32-x64.exe",
     "n'est plus installée sur la tour (mise à jour interrompue ?) : lance l'installeur resté sur la tour"),
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=False\nTACHE=1\nAPPLI=False\nEN_ATTENTE=", "réinstalle LM Studio"),
    ("SESSION=TOUR\\moi\nLMS=True\nBIONIC=False\nTACHE=1\nAPPLI=True\nEN_ATTENTE=", "a échoué (code 1)"),
])
def test_lire_diagnostic(sortie, attendu):
    assert attendu in tour.lire_diagnostic(sortie)


class TestOuvrirLmstudio:
    @pytest.fixture
    def tour_simulee(self, monkeypatch):
        vu = {"scripts": []}
        monkeypatch.setattr(tour.time, "sleep", lambda s: None)
        monkeypatch.setattr(tour, "lmstudio_ok", lambda: vu.get("pret", False))

        def ps(script, timeout=90):
            vu["scripts"].append(script)
            if "SESSION=" in script:                              # diagnostic
                return resultat("SESSION=\nLMS=True\nBIONIC=False\nTACHE=0")
            return resultat("TACHE_LANCEE\r\n", CLIXML)
        monkeypatch.setattr(tour, "ps_distant", ps)
        return vu

    def test_tache_recreee_a_chaque_fois(self, tour_simulee):
        tour_simulee["pret"] = True
        assert tour.ouvrir_lmstudio_tour(log=lambda m: None)
        script = tour_simulee["scripts"][0]
        assert "-Force" in script and "Get-ScheduledTask -TaskName" not in script     # plus de « si absente seulement »
        assert "$ProgressPreference = 'SilentlyContinue'" in script and str(tour.T["port_serveur"]) in script

    def test_echec_avec_diagnostic(self, tour_simulee):
        messages = []
        assert not tour.ouvrir_lmstudio_tour(log=messages.append)
        assert "aucune session Windows n'est ouverte" in messages[-1] and "CLIXML" not in messages[-1]

    def test_script_non_lance(self, monkeypatch):
        monkeypatch.setattr(tour, "ps_distant", lambda script, timeout=90: None)
        messages = []
        assert not tour.ouvrir_lmstudio_tour(log=messages.append)
        assert "pas de réponse SSH" in messages[-1]
