"""Page Rapport : bilan d'après le tableau (rapport_tableau) et les journaux (rapport_journal)."""
from datetime import date, timedelta

import rapport
import rapport_journal
import rapport_tableau

AUJ = date.today()
JOURNAL = """[09:00:00] ===== ROUTINE ALTERNANCE (tout) =====
[09:00:05] 🧠 Modèle utilisé : tour (http://127.0.0.1:1234/v1)
[09:01:00]    🚫 Lyon : 4 entreprise(s) hors informatique écartée(s) (Boulangerie Exemple (Boulangerie))
[09:02:00]    📝 Forgeval Dev : candidature en brouillon (Brouillon)
[09:02:30]    📝 Pixelo : lettre prête, à postuler sur la page « À postuler » (À postuler (La Bonne Alternance))
[09:03:00]    📝 Comptanova : relance 1 en brouillon — à planifier dans Outlook pour le lun. 01/12 à 09:00
[09:03:10]    📩 Pixelmont : réponse [refus] La société ne donne pas suite
[09:03:20]    ✉️  Lambert-Morel : envoyé le 20/11
[09:03:30]    🔁 Comptanova : relance envoyée le 18/11
[09:03:40]    ⚠️ Pixelo : rédaction impossible (timed out)
[09:04:00] ✅ Routine « tout » terminée en 4 min (modèle : tour). Les brouillons sont dans Outlook.
[10:00:00] ===== ROUTINE ALTERNANCE (recherche, essai) =====
[10:00:30]    📝 Essai SA : candidature en brouillon (Brouillon)
[10:01:00] ✅ Routine « recherche » terminée en 1 min (modèle : tour).
"""


def journaux(tmp_path, monkeypatch, jours):
    logs = tmp_path / "logs_rapport"
    logs.mkdir()
    for j in jours:
        (logs / f"{j:%Y-%m-%d}.log").write_text(JOURNAL, encoding="utf-8")
    (logs / "ovms.log").write_text("📝 ignoré", encoding="utf-8")
    monkeypatch.setattr(rapport_journal, "LOGS", logs)


def test_journal_compte_les_routines_sans_les_essais(tmp_path, monkeypatch):
    journaux(tmp_path, monkeypatch, [AUJ, AUJ - timedelta(days=40)])
    j = rapport_journal.resumer(AUJ - timedelta(days=6), AUJ)
    assert j["jours"] == 1 and j["essais"] == 1
    assert j["routines"] == {"tout": 1} and j["minutes"] == 4
    assert (j["candidatures"], j["lettres"], j["relances_brouillon"]) == (1, 1, 1)
    assert (j["envois_vus"], j["relances_vues"]) == (1, 1)
    assert j["reponses"] == {"refus": 1} and j["machines"] == {"tour": 1}
    assert j["problemes"] == ["⚠️ Pixelo : rédaction impossible (timed out)"]
    assert rapport_journal.resumer(AUJ - timedelta(days=60), AUJ)["jours"] == 2


def lignes():
    return [
        {"Entreprise": "Forgeval Dev", "Statut": "Candidaté (mail)", "Date envoi": AUJ - timedelta(days=2),
         "Date ajout": AUJ - timedelta(days=3), "Source": "La Bonne Alternance (spontanée)", "Relance prévue": AUJ + timedelta(days=5)},
        {"Entreprise": "Pixelo", "Statut": "Entretien", "Date envoi": AUJ - timedelta(days=4), "Dernière action": AUJ - timedelta(days=1),
         "Source": "LinkedIn"},
        {"Entreprise": "Comptanova", "Statut": "Refus", "Date envoi": AUJ - timedelta(days=50), "Dernière action": AUJ - timedelta(days=3)},
        {"Entreprise": "Pixelmont", "Statut": "Candidaté (La Bonne Alternance)", "Date envoi": AUJ - timedelta(days=100)},
        {"Entreprise": "Lambert-Morel", "Statut": "Brouillon", "Date ajout": AUJ},
    ]


def test_tableau_sur_la_periode():
    t = rapport_tableau.resumer(lignes(), AUJ - timedelta(days=6), AUJ)
    assert t["envoyees"] == 2 and t["ajoutees"] == 2
    assert dict(t["par_canal"]) == {"mail": 2} and dict(t["par_source"]) == {"La Bonne Alternance": 1, "LinkedIn": 1}
    assert t["reponses"] == 2 and t["entretiens"] == 1 and t["refus"] == 1   # réponses reçues dans la période
    assert t["taux"] == 50                                                    # 1 des 2 candidatures de la période
    assert [l["Entreprise"] for l in t["relances"]] == ["Forgeval Dev"]
    assert t["total"] == 5 and t["a_postuler"] == 1


def test_periode():
    assert rapport.periode({}) == (AUJ - timedelta(days=29), AUJ, "30")
    assert rapport.periode({"jours": "7"})[0] == AUJ - timedelta(days=6)
    assert rapport.periode({"jours": "abc"})[2] == "30"
    assert rapport.periode({"du": "2026-11-20", "au": "2026-11-01"}) == (date(2026, 11, 1), date(2026, 11, 20), "dates")
    assert rapport.periode({"du": "pas une date", "au": "2026-11-01"})[2] == "30"


def test_ecartees_comptees_une_fois():
    import refus
    refus.noter([{"Entreprise": "Boulangerie Exemple", "SIRET": "12345678900011", "Code NAF": "10.71C",
                  "Activité": "Boulangerie", "Adresse": "69003 Lyon", "Recherche": "Lyon"}])
    refus.noter([{"Entreprise": "Boulangerie Exemple", "SIRET": "12345678900011", "Code NAF": "10.71C",
                  "Activité": "Boulangerie", "Adresse": "69003 Lyon", "Recherche": "Lyon"}])
    assert rapport.ecartees(AUJ - timedelta(days=6), AUJ) == 1
    assert rapport.ecartees(AUJ - timedelta(days=60), AUJ - timedelta(days=30)) == 0


def test_depuis_le_debut_et_texte(tmp_path, monkeypatch):
    journaux(tmp_path, monkeypatch, [AUJ])
    r = rapport.generer({"jours": "0"}, lignes())
    assert r["debut"] == AUJ - timedelta(days=100) and r["t"]["envoyees"] == 4
    texte = rapport.texte(r)
    assert "Candidatures envoyées : 4" in texte and "Forgeval Dev" in texte and "Pixelo : Entretien" in texte


def test_page_rapport(client, tableau, tmp_path, monkeypatch):
    tableau.save()
    journaux(tmp_path, monkeypatch, [AUJ])
    client.post("/api/suivi/ajouter", json={"Entreprise": "Pixelmont", "Statut": "Candidaté (autre canal)",
                                            "Date envoi": AUJ.isoformat()})
    html = client.get("/rapport?jours=7").get_data(as_text=True)
    assert "Rapport de recherche" in html and "Pixelmont" in html and "Activité des routines" in html
    assert "1 routine(s) en essai" in html
    assert client.get("/rapport?du=2026-01-01&au=2026-01-31").status_code == 200
