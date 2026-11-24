"""Thème de l'interface (web/src/theme.py, réglage « interface.theme ») : système par défaut, clair ou sombre."""
import commun
import theme


def test_systeme_par_defaut(client, monkeypatch):
    monkeypatch.delitem(commun.CFG, "interface", raising=False)
    assert theme.attribut() == ""
    assert "<html lang=\"fr\">" in client.get("/suivi").get_data(as_text=True)


def test_clair_ou_sombre_choisi(client, monkeypatch):
    for choix in ("clair", "sombre"):
        monkeypatch.setitem(commun.CFG, "interface", {"theme": choix})
        assert f'<html lang="fr" data-theme="{choix}">' in client.get("/suivi").get_data(as_text=True)


def test_reglage_enregistre_depuis_les_parametres(client):
    r = client.post("/api/reglages", json={"valeurs": {"alternance|interface.theme": "sombre"}}).get_json()
    assert r["ok"] and theme.attribut() == "sombre"
    assert 'data-theme="sombre"' in client.get("/").get_data(as_text=True)
    assert not client.post("/api/reglages", json={"valeurs": {"alternance|interface.theme": "bleu"}}).get_json()["ok"]


def test_config_absente_theme_du_systeme(monkeypatch):
    import reglages
    monkeypatch.setattr(reglages, "valeur", lambda c: (_ for _ in ()).throw(FileNotFoundError()))
    assert theme.attribut() == ""


def test_style_suit_le_reglage_puis_le_systeme():
    import emplacements
    css = (emplacements.RESSOURCES / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert ':root:not([data-theme="clair"])' in css and ':root[data-theme="sombre"]' in css
