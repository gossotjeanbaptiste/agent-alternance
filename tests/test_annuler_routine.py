"""Bouton « Annuler » de la page Routines (routines.annuler) et enregistrements sans fichier abîmé.
L'arrêt est testé sur un faux arbre de processus local (aucune vraie routine, aucun modèle)."""
import io
import json
import subprocess
import sys
import time

import pytest

import reponses
import routines


@pytest.fixture
def routine_factice(tmp_path, monkeypatch):
    """Un processus « boucle » qui lance un « passage » enfant, comme lmagent --routine … --fois N."""
    pid_enfant = tmp_path / "enfant.pid"
    parent = ("import subprocess, sys, time; "
              "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
              f"open(r'{pid_enfant}', 'w').write(str(c.pid)); time.sleep(120)")
    journal = tmp_path / "web_routine.txt"
    journal.write_text("passage 1…\n", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-c", parent], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(100):
        if pid_enfant.exists() and pid_enfant.read_text():
            break
        time.sleep(0.1)
    dechargements = []
    monkeypatch.setattr(routines, "decharger_modele", lambda: dechargements.append(1))
    monkeypatch.setitem(routines.ROUTINE, "proc", p)
    monkeypatch.setitem(routines.ROUTINE, "fichier", journal)
    yield {"proc": p, "enfant": int(pid_enfant.read_text()), "journal": journal, "dechargements": dechargements}
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def vivant(pid):
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True)
    return str(pid) in (r.stdout or b"").decode("ascii", errors="ignore")   # sortie en page de code console


def attendre(condition, secondes=15):
    """Attend qu'une condition devienne vraie (la suite complète peut ralentir les processus)."""
    limite = time.time() + secondes
    while time.time() < limite:
        if condition():
            return True
        time.sleep(0.1)
    return condition()


def test_annuler_arrete_la_boucle_et_le_passage(routine_factice):
    assert vivant(routine_factice["enfant"])
    ok, message = routines.annuler()
    assert ok and "annulée" in message
    assert routine_factice["proc"].poll() is not None and not routines.en_cours()
    assert attendre(lambda: not vivant(routine_factice["enfant"]))     # le passage en cours aussi
    assert "⛔ Routine annulée" in routine_factice["journal"].read_text(encoding="utf-8")
    assert attendre(lambda: routine_factice["dechargements"] == [1])   # modèle déchargé ensuite
    assert routines.etat()["annulee"] is True


def test_rien_a_annuler(monkeypatch):
    monkeypatch.setitem(routines.ROUTINE, "proc", None)
    assert routines.annuler() == (False, "Aucune routine en cours.")


def test_decharger_seulement_le_modele_des_routines(monkeypatch):
    import agent
    monkeypatch.setitem(agent.CONFIG, "modele", "qwen/qwen3.5-9b")
    monkeypatch.setitem(agent.CONFIG, "serveurs", [{"nom": "tour", "url": "http://tour:1236/v1"}])
    dechargees = []

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/api/v1/models"):
            return R(json.dumps({"models": [
                {"key": "qwen/qwen3.5-9b", "loaded_instances": [{"id": "qwen-1"}]},
                {"key": "autre/modele", "loaded_instances": [{"id": "autre-1"}]}]}).encode())
        dechargees.append(json.loads(req.data)["instance_id"])
        return R(b"{}")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert routines.decharger_modele() == 1 and dechargees == ["qwen-1"]   # pas un modèle chargé à la main


def test_api_et_bouton(client, monkeypatch):
    monkeypatch.setattr(routines, "annuler", lambda: (True, "Routine annulée."))
    assert client.post("/api/annuler_routine").get_json()["ok"]
    monkeypatch.setattr(routines, "annuler", lambda: (False, "Aucune routine en cours."))
    assert client.post("/api/annuler_routine").status_code == 409
    h = client.get("/routines").get_data(as_text=True)
    assert 'id="annuler"' in h and "annulerRoutine()" in h and "routines.js" in h
    from chemins import ROOT
    assert "⛔ annulée" in (ROOT / "web" / "static" / "routines.js").read_text(encoding="utf-8")


# --- enregistrements protégés -------------------------------------------------------------------------
def test_tableau_jamais_a_moitie_ecrit(tableau, monkeypatch):
    """Arrêt (ou erreur) en plein enregistrement : l'ancien tableau reste intact."""
    tableau.add(**{"Entreprise": "Avant"})
    tableau.enregistrer_sur()
    avant = tableau.path.read_bytes()
    tableau.add(**{"Entreprise": "Après"})

    def coupe(self, chemin):
        open(chemin, "wb").write(b"PK\x03\x04 coupe")      # fichier provisoire à moitié écrit
        raise KeyboardInterrupt("arrêt en plein enregistrement")
    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", coupe)
    with pytest.raises(KeyboardInterrupt):
        tableau.enregistrer_sur()
    assert tableau.path.read_bytes() == avant


def test_tableau_ouvert_dans_excel(tableau, monkeypatch):
    tableau.enregistrer_sur()

    def verrouille(a, b):
        raise PermissionError("ouvert dans Excel")
    monkeypatch.setattr("os.replace", verrouille)
    with pytest.raises(PermissionError):
        tableau.enregistrer_sur()
    assert not list(tableau.path.parent.glob("*.enregistrement.xlsx"))   # pas de fichier provisoire oublié


def test_lettres_enregistrees_d_un_seul_coup():
    reponses.enregistrer("https://lba/1", {"lettre": "L"})
    reponses.enregistrer("https://lba/1", {"motivations": "M"})
    assert reponses.lire() == {"https://lba/1": {"lettre": "L", "motivations": "M"}}
    assert not list(reponses.FICHIER.parent.glob("*.enregistrement"))
