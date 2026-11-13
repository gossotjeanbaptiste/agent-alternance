"""Authentification de l'interface (web/src/auth.py, securite.py, routes de connexion).
Le compte vit dans le dossier de données temporaire des tests."""
import json

import pytest

import auth
import securite
from conftest import IDENTIFIANT, MOT_DE_PASSE


# --- module auth -------------------------------------------------------------------------------------
class TestCompte:
    def test_pas_de_compte_au_depart(self):
        assert not auth.compte_existe() and auth.identifiant() == ""

    def test_creation(self):
        ok, _ = auth.creer_compte("  camille  ", "un-long-mot", "un-long-mot")
        assert ok and auth.compte_existe() and auth.identifiant() == "camille"
        d = json.loads(auth.FICHIER.read_text(encoding="utf-8"))
        assert "un-long-mot" not in json.dumps(d)                 # jamais en clair
        assert d["mot_de_passe"].startswith(("scrypt:", "pbkdf2:")) and len(d["cle"]) == 64

    @pytest.mark.parametrize("ident, mdp, conf, message", [
        ("", "un-long-mot", "un-long-mot", "Identifiant"),
        ("x" * 61, "un-long-mot", "un-long-mot", "Identifiant"),
        ("camille", "court", "court", "trop court"),
        ("camille", "un-long-mot", "autre-mot!", "pas identiques"),
    ])
    def test_creation_refusee(self, ident, mdp, conf, message):
        ok, msg = auth.creer_compte(ident, mdp, conf)
        assert not ok and message in msg and not auth.compte_existe()

    def test_un_seul_compte(self):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        ok, msg = auth.creer_compte("pirate", "autre-long-mot", "autre-long-mot")
        assert not ok and auth.identifiant() == "camille"

    def test_verifier(self):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        assert auth.verifier("camille", "un-long-mot")[0]
        assert auth.verifier(" camille ", "un-long-mot")[0]
        assert not auth.verifier("camille", "mauvais")[0]
        assert not auth.verifier("autre", "un-long-mot")[0]
        assert not auth.verifier("", "")[0]

    def test_sans_compte_rien_n_est_accepte(self):
        assert not auth.verifier("", "")[0]

    def test_frein_aux_essais_repetes(self, monkeypatch):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        horloge = [1000.0]
        monkeypatch.setattr(auth.time, "time", lambda: horloge[0])
        for _ in range(auth.ESSAIS_LIBRES):
            assert not auth.verifier("camille", "faux")[0]
        ok, msg = auth.verifier("camille", "un-long-mot")      # même le bon mot de passe attend
        assert not ok and "réessaie dans 30 s" in msg
        horloge[0] += 31
        assert not auth.verifier("camille", "faux")[0]          # 6e échec : 60 s
        assert "60 s" in auth.verifier("camille", "un-long-mot")[1]
        horloge[0] += 61
        assert auth.verifier("camille", "un-long-mot")[0]
        assert auth.ECHECS == {"nb": 0, "jusqua": 0.0}          # remis à zéro après un succès

    def test_changer_mot_de_passe(self):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        cle_avant = auth.cle_secrete()
        assert not auth.changer_mot_de_passe("faux", "nouveau-mot", "nouveau-mot")[0]
        assert not auth.changer_mot_de_passe("un-long-mot", "court", "court")[0]
        assert not auth.changer_mot_de_passe("un-long-mot", "nouveau-mot", "different")[0]
        assert auth.changer_mot_de_passe("un-long-mot", "nouveau-mot", "nouveau-mot")[0]
        assert auth.verifier("camille", "nouveau-mot")[0] and not auth.verifier("camille", "un-long-mot")[0]
        assert auth.cle_secrete() != cle_avant                  # autres sessions déconnectées

    def test_cle_secrete_stable(self):
        assert auth.cle_secrete() == auth.cle_secrete()

    def test_fichier_illisible(self):
        auth.FICHIER.write_text("{cassé", encoding="utf-8")
        assert not auth.compte_existe()


class TestSuiteSure:
    @pytest.mark.parametrize("suite, attendu", [
        ("/suivi", "/suivi"), ("/postuler?x=1", "/postuler?x=1"), (None, "/"), ("", "/"),
        ("https://pirate.example", "/"), ("//pirate.example", "/"), ("/\\pirate.example", "/"),
    ])
    def test_retour_seulement_dans_l_interface(self, suite, attendu):
        assert securite.suite_sure(suite) == attendu


# --- interface -----------------------------------------------------------------------------------------
class TestAccesSansConnexion:
    @pytest.mark.parametrize("url", ["/", "/suivi", "/postuler", "/parametres", "/routines", "/journal", "/linkedin"])
    def test_pages_renvoient_vers_la_connexion(self, anonyme, url):
        r = anonyme.get(url)
        assert r.status_code == 302 and "/connexion" in r.headers["Location"]

    def test_page_d_origine_retenue(self, anonyme):
        assert anonyme.get("/suivi").headers["Location"].endswith("/connexion?suite=/suivi")

    @pytest.mark.parametrize("url", ["/api/statut", "/api/reglages", "/api/interdits", "/api/routine/relances",
                                     "/api/quitter", "/api/mot_de_passe"])
    def test_actions_refusees(self, anonyme, url):
        r = anonyme.post(url, json={})
        assert r.status_code == 401 and r.get_json()["connexion"] is True

    def test_lecture_api_refusee(self, anonyme):
        assert anonyme.get("/api/routine").status_code == 401

    def test_fichiers_statiques_libres(self, anonyme):
        for f in ("logo.png", "style.css", "favicon.ico"):
            assert anonyme.get(f"/static/{f}").status_code == 200

    def test_page_de_creation_au_premier_lancement(self, anonyme):
        h = anonyme.get("/connexion").get_data(as_text=True)
        assert "Créer le compte" in h and "confirmation" in h and securite.JETON in h

    def test_page_de_connexion_ensuite(self, anonyme):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        h = anonyme.get("/connexion").get_data(as_text=True)
        assert "Se connecter" in h and 'id="confirmation"' not in h and 'value="camille"' in h

    def test_connexion_exige_le_jeton(self, anonyme):
        r = anonyme.post("/api/connexion", json={"identifiant": "x", "mot_de_passe": "y"}, jeton=False)
        assert r.status_code == 403


class TestConnexion:
    def test_creation_puis_acces(self, anonyme):
        r = anonyme.post("/api/connexion", json={"identifiant": "camille", "mot_de_passe": "un-long-mot",
                                                 "confirmation": "un-long-mot"})
        assert r.status_code == 200 and r.get_json()["ok"]
        assert anonyme.get("/").status_code == 200
        assert anonyme.get("/connexion?suite=/suivi").headers["Location"].endswith("/suivi")   # déjà connecté

    def test_creation_refusee(self, anonyme):
        r = anonyme.post("/api/connexion", json={"identifiant": "camille", "mot_de_passe": "court", "confirmation": "court"})
        assert r.status_code == 401 and "trop court" in r.get_json()["message"]
        assert not auth.compte_existe()

    def test_mauvais_mot_de_passe(self, anonyme):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        r = anonyme.post("/api/connexion", json={"identifiant": "camille", "mot_de_passe": "faux"})
        assert r.status_code == 401 and "incorrect" in r.get_json()["message"]
        assert anonyme.get("/").status_code == 302

    def test_session_et_cookie(self, anonyme):
        auth.creer_compte("camille", "un-long-mot", "un-long-mot")
        r = anonyme.post("/api/connexion", json={"identifiant": "camille", "mot_de_passe": "un-long-mot", "rester": True})
        cookie = r.headers.get("Set-Cookie", "")
        assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Expires=" in cookie   # 30 jours
        r = anonyme.post("/api/connexion", json={"identifiant": "camille", "mot_de_passe": "un-long-mot"})
        assert "Expires=" not in r.headers.get("Set-Cookie", "")                              # fin du navigateur

    def test_deconnexion(self, client):
        assert client.get("/").status_code == 200
        assert client.post("/api/deconnexion").get_json()["ok"]
        assert client.get("/").status_code == 302

    def test_compte_supprime_sessions_invalides(self, client):
        auth.FICHIER.unlink()
        r = client.get("/")
        assert r.status_code == 302                              # retour à la page de création

    def test_bouton_se_deconnecter(self, client):
        h = client.get("/").get_data(as_text=True)
        assert "Se déconnecter" in h and "deconnecter()" in h

    def test_changer_le_mot_de_passe_garde_cette_session(self, client, appli):
        r = client.post("/api/mot_de_passe", json={"actuel": MOT_DE_PASSE, "nouveau": "tout-nouveau-mot",
                                                   "confirmation": "tout-nouveau-mot"})
        assert r.status_code == 200 and r.get_json()["ok"]
        assert client.get("/").status_code == 200                # toujours connecté ici
        assert appli.secret_key == auth.cle_secrete()
        assert auth.verifier(IDENTIFIANT, "tout-nouveau-mot")[0]

    def test_changer_le_mot_de_passe_refuse(self, client):
        r = client.post("/api/mot_de_passe", json={"actuel": "faux", "nouveau": "tout-nouveau-mot",
                                                   "confirmation": "tout-nouveau-mot"})
        assert r.status_code == 400 and "incorrect" in r.get_json()["message"]

    def test_autre_navigateur_deconnecte_apres_changement(self, appli):
        from conftest import _client
        a, b = _client(appli), _client(appli)
        for c in (a, b):
            c.post("/api/connexion", json={"identifiant": IDENTIFIANT, "mot_de_passe": MOT_DE_PASSE,
                                           "confirmation": MOT_DE_PASSE})
        assert b.get("/").status_code == 200
        a.post("/api/mot_de_passe", json={"actuel": MOT_DE_PASSE, "nouveau": "tout-nouveau-mot",
                                          "confirmation": "tout-nouveau-mot"})
        assert a.get("/").status_code == 200
        assert b.get("/").status_code == 302

    def test_cartes_repliables_dans_les_parametres(self, client):
        h = client.get("/parametres").get_data(as_text=True)
        for ident in ("pli-signature", "pli-signature-mails", "pli-interdits", "pli-mot-de-passe"):
            assert f'<details class="carte pli-section" id="{ident}">' in h
        assert "Mot de passe de l'interface" in h and IDENTIFIANT in h
