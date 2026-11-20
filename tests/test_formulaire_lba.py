"""Formulaire La Bonne Alternance prérempli (alternance/src/formulaire_lba.py, web/src/formulaire_web.py) et client
Chrome (src/chrome/). Chrome n'est jamais lancé : l'onglet est simulé."""
import pytest

import formulaire_lba as f
import formulaire_lba_chrome as fc


@pytest.mark.parametrize("complet, attendu", [
    ("Marc FORGEVAL", ("FORGEVAL", "Marc")),
    ("Marc-Antoine DE LA FORGE", ("DE LA FORGE", "Marc-Antoine")),
    ("Marc Forgeval", ("Forgeval", "Marc")),
    ("", ("", "")),
])
def test_nom_et_prenom(complet, attendu):
    assert f.nom_et_prenom(complet) == attendu


def test_choisir_cv(tmp_path):
    lettre = tmp_path / "Lettre.pdf"
    cv = tmp_path / "CV_Marc.pdf"
    calendrier = tmp_path / "calendrier.png"
    gros = tmp_path / "cv_complet.pdf"
    for p in (lettre, cv, calendrier):
        p.write_bytes(b"x")
    gros.write_bytes(b"x" * (f.TAILLE_CV_MAX + 1))       # trop gros pour le site
    assert f.choisir_cv([calendrier, lettre, gros, cv]) == cv
    assert f.choisir_cv([calendrier, lettre]) == lettre    # pas de « cv » dans le nom : le premier PDF qui convient
    assert f.choisir_cv([calendrier, tmp_path / "absent.pdf"]) is None


@pytest.mark.parametrize("intitule, cle", [
    ("Pourquoi souhaitez-vous rejoindre notre entreprise ?", "motivations"),
    ("Quelles missions souhaiteriez-vous accomplir au sein de l’entreprise ?", "missions"),
    ("Décrivez vos expériences passées (stage, job, bénévolat)", "experiences"),
    ("Votre couleur préférée ?", None),
])
def test_cle_question(intitule, cle):
    assert f.cle_question(intitule) == cle


def test_champs(cfg, monkeypatch):
    cfg["signature_formulaire"] = {"nom": "Marc FORGEVAL", "email": "marc@exemple.fr", "telephone": "+33 6 12 34 56 78"}
    monkeypatch.setitem(cfg, "la_bonne_alternance", {**cfg.get("la_bonne_alternance", {}),
                                                     "situation": "pas encore inscrit(e) en formation"})
    d = f.champs("Madame, Monsieur,\nTexte.", {"motivations": "Parce que.", "lettre": "doublon"})
    assert d["applicant_last_name"] == "FORGEVAL" and d["applicant_first_name"] == "Marc"
    assert d["applicant_phone"] == "+33612345678" and d["applicant_email"] == "marc@exemple.fr"
    assert d["situation"] == 1 and d["reponses"] == {"motivations": "Parce que."}
    assert d["applicant_message"].startswith("Madame")
    assert d["debut"] == [] and d["duree"] == "" and d["applicant_formation_description"] == ""


def test_recherche_d_alternance(cfg, monkeypatch):
    """Les réglages « Ma recherche d'alternance » passent au formulaire (école et rythme coupés à 200 caractères)."""
    monkeypatch.setitem(cfg, "la_bonne_alternance", {**cfg.get("la_bonne_alternance", {}),
                        "situation": "déjà inscrit(e) en formation", "debut_contrat": ["Dès que possible", " "],
                        "duree_contrat": "12 mois", "formation": "École Exemple Grenoble, 3e année " + "x" * 300,
                        "rythme": "1 mois en entreprise / 2 semaines à l'école"})
    d = f.champs("", {})
    assert d["situation"] == 0 and d["debut"] == ["Dès que possible"] and d["duree"] == "12 mois"
    assert len(d["applicant_formation_description"]) == f.LIMITE_RECHERCHE
    assert d["applicant_rythm_description"] == "1 mois en entreprise / 2 semaines à l'école"


def test_cv_des_parametres(cfg, monkeypatch, tmp_path):
    import commun
    dossier = commun.donnees.emplacements.dossier("pieces_jointes")
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "CV+Calendrier.pdf").write_bytes(b"%PDF")
    monkeypatch.setitem(cfg, "la_bonne_alternance", {**cfg.get("la_bonne_alternance", {}), "cv": "CV+Calendrier.pdf"})
    assert f.cv_du_formulaire() == (dossier / "CV+Calendrier.pdf", "")          # simple nom : cherché dans pieces_jointes
    monkeypatch.setitem(cfg["la_bonne_alternance"], "cv", str(tmp_path / "absent.pdf"))
    cv, remarque = f.cv_du_formulaire()
    assert "introuvable" in remarque


class FauxOnglet:
    """Onglet Chrome simulé : lmagentRemplir (remplir.js) renvoie la réponse préparée."""
    def __init__(self, reponse=None):
        self.reponse = reponse or {"ok": True, "faits": ["applicant_last_name", "motivations", "cv"]}
        self.js, self.ferme = [], False

    def montrer(self):
        pass

    def attendre(self, js, delai=20, pas=0.5):
        return True

    def evaluer(self, js):
        self.js.append(js)
        return self.reponse if js.startswith("lmagentRemplir(") else None

    def fermer(self):
        self.ferme = True


@pytest.fixture
def onglet(monkeypatch):
    import chrome
    o = FauxOnglet()
    monkeypatch.setattr(chrome, "ouvrir", lambda url: o)
    return o


def test_remplit_sans_jamais_envoyer(onglet):
    ok, message = fc.ouvrir_et_remplir("https://lba.example/fiche", {"reponses": {}, "cv": {"nom": "CV.pdf"}})
    assert ok and "CV joint (CV.pdf)" in message and onglet.ferme
    assert "lmagentRemplir" in onglet.js[0]                       # le code de remplissage partagé (remplir.js)
    code = "\n".join(l for l in fc.REMPLIR.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("//"))
    assert "envoie" not in code.lower() and "submit" not in code.lower()  # jamais de clic d'envoi (hors commentaires)


def test_entreprise_sans_contact(onglet):
    onglet.reponse = {"ok": False, "raison": "sans_contact"}
    ok, message = fc.ouvrir_et_remplir("https://lba.example/fiche", {})
    assert not ok and "plus de contact" in message and onglet.ferme


def test_sans_cv(onglet):
    onglet.reponse = {"ok": True, "faits": ["applicant_last_name"]}
    ok, message = fc.ouvrir_et_remplir("https://lba.example/fiche", {"reponses": {}, "cv": None})
    assert ok and "joins-le à la main" in message


def test_cv_pour_le_navigateur(tmp_path):
    import base64
    cv = tmp_path / "CV.pdf"
    cv.write_bytes(b"%PDF-essai")
    d = f.cv_pour_le_navigateur(cv)
    assert d["nom"] == "CV.pdf" and d["type"] == "application/pdf" and base64.b64decode(d["contenu"]) == b"%PDF-essai"
    assert f.cv_pour_le_navigateur(None) is None


# --- page À postuler et point d'API -----------------------------------------------------------------
@pytest.fixture
def sans_outlook(monkeypatch):
    import lettres
    monkeypatch.setattr(lettres, "_outlook_ferme", lambda: True)
    monkeypatch.setitem(lettres.CACHE, "quand", 0)


def ligne_lba(tableau, **v):
    from tableau import LBA
    tableau.add(**{"Entreprise": "Pixelo", "Statut": LBA, "Lien": "https://lba.example/pixelo", **v})
    tableau.save()
    return next(r[0].row for r in tableau.rows() if tableau.get(r, "Entreprise") == "Pixelo")


def test_bouton_seulement_pour_la_bonne_alternance(client, tableau, sans_outlook):
    from tableau import FORMULAIRE
    ligne_lba(tableau)
    tableau.add(**{"Entreprise": "Brio", "Statut": FORMULAIRE, "Lien": "https://brio.example/contact"})
    tableau.save()
    h = client.get("/postuler").get_data(as_text=True)
    assert h.count("ouvrirFormulaire(this") == 1 and "Ouvrir le formulaire prérempli" in h


def test_api_remplit_avec_lettre_reponses_et_cv(client, tableau, cfg, sans_outlook, monkeypatch, tmp_path):
    import reponses
    cv = tmp_path / "CV.pdf"
    cv.write_bytes(b"%PDF")
    cfg["pieces_jointes"] = [str(cv)]
    n = ligne_lba(tableau)
    reponses.enregistrer("https://lba.example/pixelo", {"lettre": "Lettre pour Pixelo", "motivations": "Parce que"})
    cfg.setdefault("la_bonne_alternance", {})["ouverture"] = "Chrome à part (piloté par LMAgent)"
    vu = {}
    monkeypatch.setattr(fc, "ouvrir_et_remplir", lambda lien, d: vu.update(lien=lien, d=d) or (True, "Prérempli."))
    r = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Pixelo"})
    assert r.status_code == 200 and r.get_json()["ok"]
    assert vu["lien"] == "https://lba.example/pixelo" and vu["d"]["cv"]["nom"] == "CV.pdf"
    assert vu["d"]["applicant_message"].startswith("Lettre pour Pixelo") and vu["d"]["reponses"] == {"motivations": "Parce que"}


def test_api_refuse_une_autre_ligne(client, tableau, sans_outlook):
    n = ligne_lba(tableau)
    r = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Autre"})
    assert r.status_code == 400 and "introuvable" in r.get_json()["message"]


def test_api_signale_ce_qui_manque(client, tableau, sans_outlook, monkeypatch):
    n = ligne_lba(tableau)
    import extension_lba
    monkeypatch.setattr(extension_lba, "ouvrir_dans_chrome", lambda lien, jeton, port: None)
    m = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Pixelo"}).get_json()["message"]
    assert "pas encore de la lettre ni de les réponses" in m


# --- client WebSocket de Chrome -------------------------------------------------------------------------
def test_websocket_trames():
    """Une trame envoyée (masquée) est relue telle quelle par le décodeur, y compris longue (> 65 535 octets)."""
    import socket
    from chrome.websocket import WebSocket
    a, b = socket.socketpair()
    ws = object.__new__(WebSocket)
    ws.sock, ws._reste = a, b""
    lecteur = object.__new__(WebSocket)
    lecteur.sock, lecteur._reste = b, b""
    for texte in ("bonjour é", "x" * 70000):
        ws.envoyer(texte)
        assert lecteur.recevoir() == texte
    a.close()
    b.close()



# --- extension Chrome : jeton à usage unique, origine vérifiée ------------------------------------------
@pytest.fixture
def ouvert(monkeypatch):
    """Ce que LMAgent ouvrirait dans le Chrome habituel (rien n'est lancé)."""
    import extension_lba
    vu = {}
    monkeypatch.setattr(extension_lba, "ouvrir_dans_chrome", lambda lien, jeton, port: vu.update(lien=lien, jeton=jeton, port=port))
    monkeypatch.setattr(extension_lba, "EN_ATTENTE", {})
    return vu


def test_extension_recoit_les_donnees_une_seule_fois(client, tableau, sans_outlook, ouvert, appli):
    import extension_lba
    n = ligne_lba(tableau)
    r = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Pixelo"})
    assert r.get_json()["ok"] and "extension LMAgent" in r.get_json()["message"]
    assert ouvert["lien"] == "https://lba.example/pixelo" and len(ouvert["jeton"]) >= 40
    brut = appli.test_client()                      # l'extension : ni session, ni jeton d'interface
    url = f"/api/extension/{ouvert['jeton']}"
    entetes = {"Host": "127.0.0.1:8765", "Origin": extension_lba.ORIGINE}
    r = brut.post(url, headers=entetes)
    assert r.status_code == 200 and r.get_json()["donnees"]["applicant_last_name"] is not None
    assert r.headers["Cache-Control"] == "no-store"
    assert brut.post(url, headers=entetes).status_code == 404           # une seule fois


@pytest.mark.parametrize("origine", ["https://pirate.example", "chrome-extension://autreextensionautreextension", None])
def test_extension_refuse_une_autre_origine(client, tableau, sans_outlook, ouvert, appli, origine):
    import extension_lba
    ligne = ligne_lba(tableau)
    client.post("/api/formulaire", json={"ligne": ligne, "entreprise": "Pixelo"})
    entetes = {"Host": "127.0.0.1:8765", **({"Origin": origine} if origine else {})}
    assert appli.test_client().post(f"/api/extension/{ouvert['jeton']}", headers=entetes).status_code == 404
    # le jeton n'est pas consommé par la tentative : l'extension peut encore l'utiliser
    r = appli.test_client().post(f"/api/extension/{ouvert['jeton']}",
                                 headers={"Host": "127.0.0.1:8765", "Origin": extension_lba.ORIGINE})
    assert r.status_code == 200


def test_jeton_perime(monkeypatch):
    import extension_lba
    monkeypatch.setattr(extension_lba, "EN_ATTENTE", {})
    jeton = extension_lba.deposer({"x": 1})
    monkeypatch.setattr(extension_lba.time, "time", lambda: 10 ** 12)          # bien plus tard
    assert extension_lba.retirer(jeton, extension_lba.ORIGINE) is None


def test_extension_hote_etranger_refuse(appli):
    import extension_lba
    r = appli.test_client().post("/api/extension/" + "a" * 43,
                                 headers={"Host": "pirate.example", "Origin": extension_lba.ORIGINE})
    assert r.status_code == 403


def test_manifest_minimal_et_identifiant():
    """Aucune permission sur les cookies, onglets ou autres sites ; l'identifiant vient bien de la clé du manifest."""
    import base64
    import hashlib
    import json
    import extension_lba
    m = json.loads((extension_lba.SOURCE / "manifest.json").read_text(encoding="utf-8"))
    assert m["permissions"] == [] and m["host_permissions"] == ["http://127.0.0.1/*"]
    assert [c["matches"] for c in m["content_scripts"]] == [["https://labonnealternance.apprentissage.beta.gouv.fr/*"]]
    ident = "".join(chr(ord("a") + int(c, 16)) for c in hashlib.sha256(base64.b64decode(m["key"])).hexdigest()[:32])
    assert ident == extension_lba.ID_EXTENSION


# --- installation de l'extension : présence signalée, état affiché -----------------------------------------
@pytest.fixture
def presence(monkeypatch, tmp_path):
    import extension_lba
    monkeypatch.setattr(extension_lba, "_fichier_presence", lambda: tmp_path / "vue_le.txt")
    return extension_lba


def test_presence_signalee_par_l_extension_seulement(appli, presence):
    url, hote = "/api/extension_presente", {"Host": "127.0.0.1:8765"}
    assert appli.test_client().post(url, headers={**hote, "Origin": "https://pirate.example"}).status_code == 404
    assert presence.etat()["vue_le"] == ""
    assert appli.test_client().post(url, headers={**hote, "Origin": presence.ORIGINE}).status_code == 200
    assert presence.etat()["vue_le"] != ""


def test_page_affiche_l_etat_de_l_extension(client, tableau, sans_outlook, presence):
    h = client.get("/postuler").get_data(as_text=True)
    assert "pas encore installée" in h and 'id="pli-extension" open' in h and "dossier-extension" in h
    presence.noter_presence(presence.ORIGINE)
    h = client.get("/postuler").get_data(as_text=True)
    assert "✅ installée" in h and 'id="pli-extension" open' not in h


def test_bouton_installer(client, monkeypatch, presence):
    import subprocess
    import chrome
    lance = []
    monkeypatch.setattr(chrome, "trouver_chrome", lambda: "chrome.exe")      # même sans Chrome installé
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **k: lance.append(cmd))
    r = client.post("/api/extension_installer", json={})
    d = r.get_json()
    assert d["ok"] and d["dossier"] and lance and lance[0][-1] == "chrome://extensions"


# --- « Postuler par La Bonne Alternance » pour une adresse à trouver ---------------------------------------
def ligne_a_trouver(tableau, lien="https://labonnealternance.apprentissage.beta.gouv.fr/emploi/recruteurs_lba/1/pixelo"):
    from tableau import ADRESSE_A_TROUVER
    tableau.add(**{"Entreprise": "Pixelo", "Statut": ADRESSE_A_TROUVER, "Lien": lien})
    tableau.save()
    return next(r[0].row for r in tableau.rows() if tableau.get(r, "Entreprise") == "Pixelo")


def test_bouton_vers_lba_fiche_siret_ou_adresse(client, tableau, sans_outlook):
    """Bouton sur une fiche La Bonne Alternance, ou sur une autre source avec SIRET ou adresse ; pas sans rien."""
    ligne_a_trouver(tableau)
    from tableau import ADRESSE_A_TROUVER
    tableau.add(**{"Entreprise": "Brio", "Statut": ADRESSE_A_TROUVER, "Lien": "", "Source": "Liste perso"})
    tableau.add(**{"Entreprise": "Comptanova", "Statut": ADRESSE_A_TROUVER, "Source": "Liste perso",
                   "Notes": "SIRET 12345678900011 | Site : https://comptanova.example"})
    tableau.add(**{"Entreprise": "Vortalis", "Statut": ADRESSE_A_TROUVER, "Lieu": "3 rue Exemple 38000 Grenoble"})
    tableau.save()
    h = client.get("/postuler").get_data(as_text=True)
    assert h.count("versLba(this") == 3
    assert h.count(", false)\" title=\"Candidater") == 1      # fiche connue : pas de recherche
    assert "d’abord cherchée" in h


def test_siret_lu_dans_les_notes():
    import lba_recherche
    assert lba_recherche.siret_de("SIRET 12345678900011 | Site : x") == "12345678900011"
    assert lba_recherche.siret_de("", None, "SIRET : 98765432100022") == "98765432100022"
    assert lba_recherche.siret_de("Site : x") == ""


@pytest.fixture
def api_lba(monkeypatch):
    """Base Adresse Nationale et API La Bonne Alternance simulées."""
    import commun
    import lba_recherche
    vu = {"items": [], "recherches": []}
    monkeypatch.setitem(commun.CFG["la_bonne_alternance"], "jeton_api", "jeton-de-test")
    monkeypatch.setitem(commun.CFG["la_bonne_alternance"], "codes_rome", ["M1805"])
    monkeypatch.setattr(lba_recherche, "coordonnees", lambda adresse: (45.19, 5.72))

    def recruteurs(lat, lon, romes):
        vu["recherches"].append(romes)
        return vu["items"] if not romes or vu.get("avec_romes", True) else []
    monkeypatch.setattr(lba_recherche, "_recruteurs", recruteurs)
    return vu


def recruteur(siret="12345678900011", nom="COMPTANOVA", recipient=True):
    return {"workplace": {"siret": siret, "name": nom, "domain": {"naf": {"label": "Programmation informatique"}}},
            "apply": {"recipient_id": "r1" if recipient else None,
                      "url": f"https://labonnealternance.apprentissage.beta.gouv.fr/emploi/recruteurs_lba/{siret}/x"}}


def test_trouvee_par_siret(api_lba):
    import lba_recherche
    api_lba["items"] = [recruteur(siret="99999999900099", nom="Comptanova"), recruteur()]
    fiche, _ = lba_recherche.trouver("Comptanova", "12345678900011", "3 rue Exemple 38000 Grenoble")
    assert fiche["lien"].endswith("/12345678900011/x") and fiche["activite"] == "Programmation informatique"


def test_trouvee_par_nom_sans_siret_et_parmi_tous_les_metiers(api_lba):
    import lba_recherche
    api_lba["items"], api_lba["avec_romes"] = [recruteur(nom="COMPTANOVA SAS")], False
    fiche, _ = lba_recherche.trouver("Comptanova", "", "3 rue Exemple 38000 Grenoble")
    assert fiche and api_lba["recherches"] == [["M1805"], []]


@pytest.mark.parametrize("items, raison", [([], "introuvable"), ([recruteur(recipient=False)], "sans formulaire")])
def test_pas_de_formulaire(api_lba, items, raison):
    import lba_recherche
    api_lba["items"] = items
    fiche, pourquoi = lba_recherche.trouver("Comptanova", "12345678900011", "3 rue Exemple 38000 Grenoble")
    assert fiche is None and raison in pourquoi


def test_vers_lba_depuis_la_liste_perso(client, tableau, sans_outlook, monkeypatch, api_lba):
    """Liste perso : fiche trouvée par le SIRET, lien et activité notés, statut La Bonne Alternance."""
    import commun
    import lettres
    import redaction
    import vers_lba
    from tableau import ADRESSE_A_TROUVER, LBA, Suivi
    tableau.add(**{"Entreprise": "Comptanova", "Statut": ADRESSE_A_TROUVER, "Source": "Liste perso",
                   "Lieu": "3 rue Exemple 38000 Grenoble", "Notes": "SIRET 12345678900011"})
    tableau.save()
    n = next(r[0].row for r in tableau.rows() if tableau.get(r, "Entreprise") == "Comptanova")
    api_lba["items"] = [recruteur()]
    monkeypatch.setattr(vers_lba, "_lettre_du_brouillon", lambda ent: "")
    monkeypatch.setattr(lettres, "supprimer_brouillons", lambda a: "")
    monkeypatch.setattr(redaction, "ecrire_ce_qui_manque", lambda n, e: (True, "c'est écrit."))
    r = client.post("/api/vers_lba", json={"ligne": n, "entreprise": "Comptanova"})
    assert r.status_code == 200
    s = Suivi(commun.chemin_tableau())
    row = next(x for x in s.rows() if s.get(x, "Entreprise") == "Comptanova")
    assert s.get(row, "Statut") == LBA and s.get(row, "Lien").endswith("/12345678900011/x")
    assert s.get(row, "Notes") == "SIRET 12345678900011 | Activité : Programmation informatique"


def test_vers_lba_introuvable_rien_ne_change(client, tableau, sans_outlook, api_lba):
    import commun
    from tableau import ADRESSE_A_TROUVER, Suivi
    tableau.add(**{"Entreprise": "Comptanova", "Statut": ADRESSE_A_TROUVER, "Lieu": "3 rue Exemple 38000 Grenoble"})
    tableau.save()
    n = next(r[0].row for r in tableau.rows() if tableau.get(r, "Entreprise") == "Comptanova")
    r = client.post("/api/vers_lba", json={"ligne": n, "entreprise": "Comptanova"})
    assert r.status_code == 400 and "introuvable sur La Bonne Alternance" in r.get_json()["message"]
    s = Suivi(commun.chemin_tableau())
    assert s.get(next(x for x in s.rows() if s.get(x, "Entreprise") == "Comptanova"), "Statut") == ADRESSE_A_TROUVER


def test_vers_lba(client, tableau, sans_outlook, monkeypatch):
    import commun
    import lettres
    import redaction
    import reponses
    import vers_lba
    from tableau import LBA, Suivi
    n = ligne_a_trouver(tableau)
    lien = tableau.get(next(tableau.rows()), "Lien")
    monkeypatch.setattr(vers_lba, "_lettre_du_brouillon", lambda ent: "Madame, Monsieur,\n\nLettre.\n\nCordialement,")
    corbeille, ecrit = [], []
    monkeypatch.setattr(lettres, "supprimer_brouillons", lambda a: corbeille.append(a) or "Brouillon mis à la corbeille.")
    monkeypatch.setattr(redaction, "ecrire_ce_qui_manque", lambda n, e: ecrit.append((n, e)) or (True, "les réponses, c'est écrit."))
    r = client.post("/api/vers_lba", json={"ligne": n, "entreprise": "Pixelo"})
    assert r.status_code == 200 and "repassée par La Bonne Alternance" in r.get_json()["message"]
    s = Suivi(commun.chemin_tableau())
    assert s.get(next(s.rows()), "Statut") == LBA
    assert reponses.lire()[lien]["lettre"].startswith("Madame") and corbeille and ecrit == [(n, "Pixelo")]


def test_vers_lba_refuse_sans_fiche(client, tableau, sans_outlook):
    n = ligne_a_trouver(tableau, lien="")
    r = client.post("/api/vers_lba", json={"ligne": n, "entreprise": "Pixelo"})
    assert r.status_code == 400
