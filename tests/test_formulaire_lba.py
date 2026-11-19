"""Formulaire La Bonne Alternance prérempli (alternance/src/formulaire_lba.py, web/src/formulaire_web.py) et client
Chrome (src/chrome/). Chrome n'est jamais lancé : l'onglet est simulé."""
import pytest

import formulaire_lba as f


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


class FauxOnglet:
    """Onglet Chrome simulé : la page a (ou non) le bouton « Candidature simplifiée »."""
    def __init__(self, bouton=True, sans_contact=False):
        self.bouton, self.sans_contact, self.js, self.joint, self.ferme = bouton, sans_contact, [], None, False

    def montrer(self):
        pass

    def attendre(self, js, delai=20, pas=0.5):
        return self.bouton

    def evaluer(self, js):
        self.js.append(js)
        if "pas d" in js:
            return self.sans_contact
        return ["applicant_last_name", "motivations"] if "saisir" in js else True

    def joindre(self, selecteur, chemin):
        self.joint = (selecteur, chemin)

    def fermer(self):
        self.ferme = True


@pytest.fixture
def onglet(monkeypatch):
    import chrome
    o = FauxOnglet()
    monkeypatch.setattr(chrome, "ouvrir", lambda url: o)
    return o


def test_remplit_sans_jamais_envoyer(onglet, tmp_path):
    cv = tmp_path / "cv.pdf"
    ok, message = f.ouvrir_et_remplir("https://lba.example/fiche", {"applicant_last_name": "X", "reponses": {}}, cv)
    assert ok and "CV joint" in message and onglet.joint == ("#applicant_attachment_name", cv) and onglet.ferme
    tout = " ".join(onglet.js)
    assert "J'envoie" not in tout and "submit" not in tout and "type=submit" not in tout   # jamais de clic d'envoi


def test_entreprise_sans_contact(onglet):
    onglet.bouton, onglet.sans_contact = False, True
    ok, message = f.ouvrir_et_remplir("https://lba.example/fiche", {}, None)
    assert not ok and "plus de contact" in message and onglet.ferme


def test_sans_cv(onglet):
    ok, message = f.ouvrir_et_remplir("https://lba.example/fiche", {"reponses": {}}, None)
    assert ok and "joins-le à la main" in message and onglet.joint is None


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
    vu = {}
    monkeypatch.setattr(f, "ouvrir_et_remplir", lambda lien, d, c: vu.update(lien=lien, d=d, cv=c) or (True, "Prérempli."))
    r = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Pixelo"})
    assert r.status_code == 200 and r.get_json()["ok"]
    assert vu["lien"] == "https://lba.example/pixelo" and vu["cv"] == cv
    assert vu["d"]["applicant_message"].startswith("Lettre pour Pixelo") and vu["d"]["reponses"] == {"motivations": "Parce que"}


def test_api_refuse_une_autre_ligne(client, tableau, sans_outlook):
    n = ligne_lba(tableau)
    r = client.post("/api/formulaire", json={"ligne": n, "entreprise": "Autre"})
    assert r.status_code == 400 and "introuvable" in r.get_json()["message"]


def test_api_signale_ce_qui_manque(client, tableau, sans_outlook, monkeypatch):
    n = ligne_lba(tableau)
    monkeypatch.setattr(f, "ouvrir_et_remplir", lambda lien, d, c: (True, "Prérempli."))
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
