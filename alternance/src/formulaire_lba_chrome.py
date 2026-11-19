"""Mode « Chrome à part » du formulaire La Bonne Alternance prérempli : une fenêtre Chrome pilotée par LMAgent
(profil à part) ouvre la fiche, puis exécute web/extension/remplir.js, le même code de remplissage que l'extension.
Ce code ne clique JAMAIS sur « J'envoie ma candidature » : l'utilisateur relit et envoie lui-même."""
import json
import sys
import time
from pathlib import Path

RACINE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
REMPLIR = RACINE / "web" / "extension" / "remplir.js"
RAISONS = {"sans_contact": "La Bonne Alternance n'a plus de contact pour cette entreprise : pas de formulaire. "
                           "La page est ouverte dans Chrome (téléphone ou site éventuels).",
           "sans_bouton": "Bouton « Candidature simplifiée » introuvable : la page est ouverte dans Chrome, "
                          "remplis-la à la main.",
           "sans_formulaire": "Le formulaire ne s'est pas ouvert : la page est dans Chrome, remplis-la à la main."}


def ouvrir_et_remplir(lien, donnees):
    """Ouvre la fiche dans le Chrome de LMAgent et remplit le formulaire (CV compris s'il est dans donnees["cv"]).
    Renvoie (ok, message)."""
    import chrome
    onglet = chrome.ouvrir(lien)
    try:
        onglet.montrer()
        r = {}
        for essai in range(2):      # la page peut se recharger juste après son ouverture : on recommence une fois
            onglet.attendre("document.readyState === 'complete'", delai=25)
            try:
                onglet.evaluer(REMPLIR.read_text(encoding="utf-8"))
                r = onglet.evaluer(f"lmagentRemplir({json.dumps(donnees)})") or {}
                break
            except RuntimeError as e:
                if essai or "context was destroyed" not in str(e):
                    raise
                time.sleep(2)
        if not r.get("ok"):
            return False, RAISONS.get(r.get("raison"), "Remplissage impossible : remplis le formulaire à la main.")
        faits = r.get("faits") or []
        message = f"Formulaire prérempli dans Chrome ({len(faits)} champs)"
        message += (f", CV joint ({donnees['cv']['nom']})" if "cv" in faits else
                    " ; aucun CV (PDF ou Word de moins de 3 Mo) : joins-le à la main")
        return True, message + ". Relis puis clique « J'envoie ma candidature spontanée », et enfin « ✅ Envoyée » ici."
    finally:
        onglet.fermer()
