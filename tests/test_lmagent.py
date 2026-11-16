"""Point d'entrée unique (lmagent.py) et routines planifiées (web/src/planification.py).
Aucune routine ne tourne vraiment : alternance, sous-processus et schtasks sont simulés."""
import subprocess
import sys
import types

import pytest

import lmagent
import planification


class TestCommandeSoi:
    def test_depuis_le_code(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        c = lmagent.commande_soi()
        assert c[0] == sys.executable and c[1].endswith("lmagent.py")

    def test_version_installee(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\Programmes\LMAgent\LMAgent.exe")
        assert lmagent.commande_soi() == [r"C:\Programmes\LMAgent\LMAgent.exe"]


class TestAiguillage:
    @pytest.fixture
    def appels(self, monkeypatch):
        vus = []
        monkeypatch.setattr(lmagent, "routine", lambda a: vus.append(("routine", a)) or 0)
        monkeypatch.setattr(lmagent, "script", lambda m, a, o: vus.append((m, sorted(o))) or 0)
        monkeypatch.setattr(lmagent, "agent", lambda a: vus.append(("agent", a)) or 0)
        monkeypatch.setattr(lmagent, "interface", lambda: vus.append(("interface",)) or 0)
        return vus

    @pytest.mark.parametrize("args, attendu", [
        ([], "interface"),
        (["--routine", "relances"], "routine"),
        (["--postuler", "--reponses"], "postuler"),
        (["--maj-tableau"], "maj_tableau"),
        (["--agent", "--tache", "trier"], "agent"),
    ])
    def test_commandes(self, appels, args, attendu):
        assert lmagent.main(args) == 0
        assert appels[0][0] == attendu


class TestRoutine:
    @pytest.fixture
    def faux_alternance(self, monkeypatch):
        vu = {}
        mod = types.ModuleType("alternance")
        mod.main = lambda mode: vu.update(mode=mode, argv=list(sys.argv))
        monkeypatch.setitem(sys.modules, "alternance", mod)
        monkeypatch.setattr(sys, "argv", list(sys.argv))
        return vu

    def test_un_passage_dans_ce_processus(self, faux_alternance):
        assert lmagent.routine(["--routine", "recherche", "--essai"]) == 0
        assert faux_alternance["mode"] == "recherche" and faux_alternance["argv"] == ["alternance", "--essai"]

    def test_plusieurs_passages_dans_des_processus_neufs(self, monkeypatch, capsys):
        lances = []
        monkeypatch.setattr(lmagent.subprocess, "call", lambda cmd, **k: lances.append(cmd) or 0)
        assert lmagent.routine(["--routine", "relances", "--fois", "3"]) == 0
        assert len(lances) == 3 and all(c[-2:] == ["--routine", "relances"] for c in lances)
        assert "Passage 3/3" in capsys.readouterr().out

    def test_code_d_erreur_garde(self, monkeypatch):
        codes = iter([0, 2, 0])
        monkeypatch.setattr(lmagent.subprocess, "call", lambda cmd, **k: next(codes))
        assert lmagent.routine(["--routine", "tout", "--fois", "3"]) == 2

    def test_essai_transmis_a_chaque_passage(self, monkeypatch):
        lances = []
        monkeypatch.setattr(lmagent.subprocess, "call", lambda cmd, **k: lances.append(cmd) or 0)
        lmagent.routine(["--routine", "relances", "--fois", "2", "--essai"])
        assert all(c[-1] == "--essai" for c in lances)

    def test_journal_dans_l_ordre(self, tmp_path):
        """Comme depuis l'interface : la boucle écrit dans un fichier, chaque passage aussi. Avant, les repères
        « Passage N/3 » étaient tous écrits en haut du fichier, par-dessus le texte des passages."""
        import os
        from pathlib import Path
        sans_console = Path(sys.executable).with_name("pythonw.exe")      # comme LMAgent.exe : pas de console
        if not sans_console.exists():
            pytest.skip("pythonw.exe introuvable")
        # passage simulé : sans sortie reçue, il écrit lui-même dans LMAGENT_SORTIE (comme lmagent.preparer_sortie)
        passage = ("import os, sys\n"
                   "if sys.stdout is None: sys.stdout = open(os.environ['LMAGENT_SORTIE'], 'a', encoding='utf-8')\n"
                   "print('texte du passage ' * 3)\n")
        script = (f"import sys, lmagent; lmagent.commande_soi = lambda: [{str(sans_console)!r}, '-c', {passage!r}]; "
                  "lmagent.routine(['--routine', 'relances', '--fois', '3'])")
        journal = tmp_path / "web_routine.txt"
        with open(journal, "w", encoding="utf-8") as sortie:
            subprocess.run([sys.executable, "-c", script], cwd=os.path.dirname(lmagent.__file__), stdout=sortie,
                           stderr=subprocess.STDOUT, check=True, env={**os.environ, "LMAGENT_SORTIE": str(journal)})
        lignes = [l for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]
        attendu = []
        for i in range(1, 4):
            attendu += [f"===== Passage {i}/3 =====", "texte du passage " * 3]
        assert [l.strip() for l in lignes] == [a.strip() for a in attendu]

    @pytest.mark.parametrize("args", [["--routine", "formatage"], ["--routine"]])
    def test_routine_inconnue(self, args):
        with pytest.raises(SystemExit):
            lmagent.routine(args)

    def test_nombre_de_passages_invalide(self, faux_alternance):
        assert lmagent.routine(["--routine", "relances", "--fois", "beaucoup"]) == 0
        assert faux_alternance["mode"] == "relances"


class TestSansConsole:
    """Exe compilé sans console (sys.stdout / sys.stderr à None, simulé : pytest capture déjà la sortie)."""

    @pytest.fixture
    def exe(self, monkeypatch, tmp_path):
        ouverts = []

        def ouvrir(*a, **k):
            f = open(*a, **k)
            ouverts.append(f)
            return f
        avant = sys.stdout, sys.stderr
        monkeypatch.setattr(lmagent, "sans_console", lambda: True)
        monkeypatch.setattr(lmagent, "open", ouvrir, raising=False)
        monkeypatch.delenv("LMAGENT_SORTIE", raising=False)
        monkeypatch.setattr(lmagent, "ouvrir_console", lambda: setattr(sys, "stdout", "console"))
        monkeypatch.setattr("emplacements.dossier", lambda nom: tmp_path / nom)
        yield tmp_path
        sys.stdout, sys.stderr = avant
        for f in ouverts:
            f.close()

    def test_interface_dans_un_fichier(self, exe):
        lmagent.preparer_sortie([])
        print("bonjour")
        sys.stdout.flush()
        f, = (exe / "logs").glob("interface_*.txt")
        assert f.read_text(encoding="utf-8") == "bonjour\n"
        assert "LMAGENT_SORTIE" not in lmagent_env()

    def test_routine_planifiee_dans_l_historique(self, exe):
        lmagent.preparer_sortie(["--routine", "relances"])
        f, = (exe / "logs").glob("web_*_relances_planifiee.txt")
        assert lmagent_env()["LMAGENT_SORTIE"] == str(f)          # transmis aux passages suivants

    def test_fichier_impose_par_l_interface(self, exe, monkeypatch):
        cible = exe / "web_routine.txt"
        monkeypatch.setenv("LMAGENT_SORTIE", str(cible))
        lmagent.preparer_sortie(["--routine", "tout"])
        print("passage")
        sys.stdout.flush()
        assert cible.read_text(encoding="utf-8") == "passage\n"

    @pytest.mark.parametrize("args", [["--postuler"], ["--maj-tableau"], ["--agent"]])
    def test_commandes_interactives_ouvrent_une_console(self, exe, args):
        lmagent.preparer_sortie(args)
        assert sys.stdout == "console" and not (exe / "logs").exists()

    def test_avec_console_rien_ne_change(self, monkeypatch):
        sortie = sys.stdout
        lmagent.preparer_sortie([])
        assert sys.stdout is sortie


def test_emojis_dans_un_fichier_recu_en_sortie(tmp_path):
    """Exe compilé (PYTHONIOENCODING ignoré) dont la sortie est un fichier reçu de l'interface ou de la boucle :
    avant, l'encodage Windows (cp1252) faisait planter le script au premier emoji (UnicodeEncodeError)."""
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    journal = tmp_path / "journal.txt"
    script = "import lmagent; lmagent.preparer_sortie(['--routine', 'recherche']); print('🧠 Modèle utilisé')"
    with open(journal, "w", encoding="utf-8") as sortie:
        r = subprocess.run([sys.executable, "-X", "utf8=0", "-c", script], cwd=os.path.dirname(lmagent.__file__),
                           stdout=sortie, stderr=subprocess.STDOUT, env=env)
    assert r.returncode == 0, journal.read_text(encoding="utf-8", errors="replace")
    assert journal.read_text(encoding="utf-8") == "🧠 Modèle utilisé\n"


def test_journal_visible_en_temps_reel(tmp_path):
    """Comme une routine lancée par l'interface : chaque ligne doit arriver dans le fichier tout de suite, pas à la
    fin du script (l'interface relit ce fichier pour afficher le journal en direct)."""
    import os
    import time
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8", "PYTHONUNBUFFERED")}
    journal = tmp_path / "journal.txt"
    script = ("import time, lmagent; lmagent.preparer_sortie(['--routine', 'recherche']); "
              "print('🔎 première ligne'); time.sleep(30)")
    with open(journal, "w", encoding="utf-8") as sortie:
        p = subprocess.Popen([sys.executable, "-c", script], cwd=os.path.dirname(lmagent.__file__),
                             stdout=sortie, stderr=subprocess.STDOUT, env=env)
        try:
            limite = time.time() + 15
            while time.time() < limite and "première ligne" not in journal.read_text(encoding="utf-8", errors="replace"):
                time.sleep(0.2)
            assert "🔎 première ligne" in journal.read_text(encoding="utf-8"), "ligne retenue en mémoire tampon"
            assert p.poll() is None                         # le script tourne encore : c'est bien du temps réel
        finally:
            p.kill()
            p.wait()


def lmagent_env():
    import os
    return os.environ


def test_script_transmet_seulement_les_options_prevues(monkeypatch):
    vu = {}
    mod = types.ModuleType("faux_script")
    mod.main = lambda: vu.update(argv=list(sys.argv))
    monkeypatch.setitem(sys.modules, "faux_script", mod)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    lmagent.script("faux_script", ["--postuler", "--reponses", "--pirate"], {"--reponses"})
    assert vu["argv"] == ["faux_script", "--reponses"]


# --- planification (schtasks simulé) ------------------------------------------------------------------
@pytest.fixture
def schtasks(monkeypatch):
    appels, reponses = [], {}

    def run(cmd, **k):
        appels.append(cmd)
        action, nom = cmd[1], cmd[3] if len(cmd) > 3 else ""
        sortie, code = reponses.get((action, nom), ("", 0 if action != "/Query" else 1))
        return subprocess.CompletedProcess(cmd, code, stdout=sortie, stderr="erreur simulée" if code else "")
    monkeypatch.setattr(planification.subprocess, "run", run)
    schtasks.appels, schtasks.reponses = appels, reponses
    return schtasks


class TestPlanification:
    def test_planifier(self, schtasks):
        ok, msg = planification.planifier("relances", "10:00")
        assert ok and "10:00" in msg
        cmd = schtasks.appels[0]
        assert cmd[:4] == ["schtasks", "/Create", "/TN", "LMAgent_relances"]
        assert cmd[cmd.index("/SC") + 1] == "DAILY" and cmd[cmd.index("/ST") + 1] == "10:00" and "/F" in cmd
        assert cmd[cmd.index("/TR") + 1].endswith("--routine relances")

    @pytest.mark.parametrize("heure", ["25:00", "10h", "", "9:5"])
    def test_heure_invalide(self, schtasks, heure):
        assert not planification.planifier("relances", heure)[0]
        assert schtasks.appels == []

    def test_routine_inconnue(self, schtasks):
        assert not planification.planifier("formatage", "10:00")[0]
        assert not planification.supprimer("formatage")[0]

    def test_echec_de_schtasks(self, schtasks):
        schtasks.reponses[("/Create", "LMAgent_relances")] = ("", 1)
        ok, msg = planification.planifier("relances", "10:00")
        assert not ok and "impossible" in msg

    def test_supprimer(self, schtasks):
        assert planification.supprimer("recherche")[0]
        assert schtasks.appels[0][:4] == ["schtasks", "/Delete", "/TN", "LMAgent_recherche"]

    def test_liste(self, schtasks):
        schtasks.reponses[("/Query", "LMAgent_relances")] = ('"\\LMAgent_relances","14/11/2026 10:00:00","Prêt"\n', 0)
        assert planification.taches() == {"relances": {"prochaine": "14/11/2026 10:00:00", "etat": "Prêt"}}

    def test_api(self, client, schtasks):
        assert client.post("/api/planification", json={"nom": "relances", "heure": "09:30"}).get_json()["ok"]
        assert client.post("/api/planification", json={"nom": "relances", "heure": ""}).get_json()["ok"]
        assert schtasks.appels[-1][1] == "/Delete"
        assert client.post("/api/planification", json={"nom": "relances", "heure": "midi"}).status_code == 400
        assert client.get("/api/planification").get_json() == {}

    def test_section_dans_la_page(self, client):
        assert 'id="pli-planification"' in client.get("/routines").get_data(as_text=True)
