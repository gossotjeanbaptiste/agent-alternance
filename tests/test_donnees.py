"""Emplacement des données personnelles et rangement automatique (alternance/src/donnees.py).
Tous les tests travaillent dans des dossiers temporaires passés en paramètre."""
import json

import donnees


def preparer(tmp_path, fichiers):
    alt = tmp_path / "alternance"
    alt.mkdir()
    for nom, contenu in fichiers.items():
        (alt / nom).write_text(contenu, encoding="utf-8")
    return alt, alt / "donnees"


def test_le_dossier_de_test_est_utilise():
    """Les tests ne voient jamais alternance/donnees/ réel."""
    assert donnees.AUTRE
    assert donnees.DONNEES != donnees.ALTERNANCE / "donnees"
    assert donnees.chemin("profil.md") == donnees.DONNEES / "profil.md"


def test_ranger_en_mode_test_ne_touche_a_rien(capsys):
    donnees.ranger()
    assert capsys.readouterr().out == ""


def test_ranger_deplace_les_fichiers_personnels(tmp_path):
    alt, dest = preparer(tmp_path, {n: n for n in donnees.PERSONNELS})
    donnees.ranger(alt, dest)
    for nom in donnees.PERSONNELS:
        assert (dest / nom).read_text(encoding="utf-8") == nom
        assert not (alt / nom).exists()


def test_ranger_laisse_les_autres_fichiers(tmp_path):
    alt, dest = preparer(tmp_path, {"recherche.py": "code", "profil.md": "profil"})
    donnees.ranger(alt, dest)
    assert (alt / "recherche.py").exists()
    assert (dest / "profil.md").exists()


def test_ranger_est_idempotent(tmp_path):
    alt, dest = preparer(tmp_path, {"profil.md": "p"})
    donnees.ranger(alt, dest)
    donnees.ranger(alt, dest)
    assert (dest / "profil.md").read_text(encoding="utf-8") == "p"


def test_fichier_en_double_signale_sans_ecraser(tmp_path, capsys):
    alt, dest = preparer(tmp_path, {"profil.md": "ancien"})
    dest.mkdir()
    (dest / "profil.md").write_text("nouveau", encoding="utf-8")
    donnees.ranger(alt, dest)
    assert (dest / "profil.md").read_text(encoding="utf-8") == "nouveau"
    assert (alt / "profil.md").read_text(encoding="utf-8") == "ancien"
    assert "en double" in capsys.readouterr().out


def test_fichier_ouvert_laisse_en_place(tmp_path, monkeypatch, capsys):
    alt, dest = preparer(tmp_path, {"suivi_alternance.xlsx": "x"})
    vrai = type(alt).rename

    def rename(self, cible):
        if self.name == "suivi_alternance.xlsx":
            raise PermissionError("ouvert dans Excel")
        return vrai(self, cible)
    monkeypatch.setattr(type(alt), "rename", rename)
    donnees.ranger(alt, dest)
    assert (alt / "suivi_alternance.xlsx").exists()
    assert "ouvert" in capsys.readouterr().out
    # en attendant, le chemin renvoyé est l'ancien emplacement
    assert donnees.chemin("suivi_alternance.xlsx", alt, dest) == alt / "suivi_alternance.xlsx"


def test_chemin_du_tableau_corrige_dans_la_config(tmp_path):
    alt, dest = preparer(tmp_path, {"suivi_alternance.xlsx": "x"})
    ancien_chemin = str(alt / "suivi_alternance.xlsx")
    (alt / "config_alternance.json").write_text(json.dumps({"tableau_suivi": ancien_chemin, "autre": 1}),
                                                encoding="utf-8")
    donnees.ranger(alt, dest)
    cfg = json.loads((dest / "config_alternance.json").read_text(encoding="utf-8"))
    assert cfg["tableau_suivi"] == str(alt / "donnees" / "suivi_alternance.xlsx").replace("\\donnees\\", "donnees/") \
        or cfg["tableau_suivi"].endswith("donnees/suivi_alternance.xlsx")
    assert cfg["autre"] == 1


def test_chemin_du_tableau_ailleurs_non_modifie(tmp_path):
    ailleurs = tmp_path / "ailleurs.xlsx"
    ailleurs.write_text("x", encoding="utf-8")
    alt, dest = preparer(tmp_path, {"config_alternance.json": json.dumps({"tableau_suivi": str(ailleurs)})})
    donnees.ranger(alt, dest)
    assert json.loads((dest / "config_alternance.json").read_text(encoding="utf-8"))["tableau_suivi"] == str(ailleurs)


def test_config_illisible_sans_plantage(tmp_path):
    alt, dest = preparer(tmp_path, {"config_alternance.json": "{pas du json"})
    donnees.ranger(alt, dest)
    assert (dest / "config_alternance.json").read_text(encoding="utf-8") == "{pas du json"


def test_chemin_prefere_le_nouvel_emplacement(tmp_path):
    alt, dest = preparer(tmp_path, {})
    assert donnees.chemin("profil.md", alt, dest) == dest / "profil.md"
