"""Les actions de l'interface (appelées par le JavaScript des pages)."""
import re
import threading
from datetime import date

from flask import Blueprint, abort, current_app, jsonify, request, session

import icone_tache
import lettres
import routines
import suivi_donnees
import tour_web
from tableau import STATUTS

api = Blueprint("api", __name__, url_prefix="/api")


@api.post("/connexion")
def connexion():
    """Premier lancement : crée le compte puis connecte ; sinon vérifie l'identifiant et le mot de passe."""
    import auth
    d = request.get_json(force=True, silent=True) or {}
    ident, mdp = str(d.get("identifiant") or ""), str(d.get("mot_de_passe") or "")
    if not auth.compte_existe():
        ok, message = auth.creer_compte(ident, mdp, str(d.get("confirmation") or ""))
        if ok:
            current_app.secret_key = auth.cle_secrete()
    else:
        ok, message = auth.verifier(ident, mdp)
    if not ok:
        return jsonify(ok=False, message=message), 401
    session.clear()
    session["connecte"] = auth.identifiant()
    session.permanent = bool(d.get("rester"))
    return jsonify(ok=True, message=message)


@api.post("/assistant/<etape>")
def assistant(etape):
    import assistant as a
    if etape not in a.ETAPES:
        abort(404)
    d = request.get_json(force=True, silent=True) or {}
    ok, message = a.ETAPES[etape](d)
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/assistant_cv")
def assistant_cv():
    import assistant as a
    ok, message = a.etape_cv(request.files.get("fichier"))
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/deconnexion")
def deconnexion():
    session.clear()
    return jsonify(ok=True, message="Déconnecté.")


@api.post("/mot_de_passe")
def mot_de_passe():
    """Change le mot de passe ; les autres sessions (autres navigateurs) sont déconnectées, pas celle-ci."""
    import auth
    d = request.get_json(force=True, silent=True) or {}
    ok, message = auth.changer_mot_de_passe(str(d.get("actuel") or ""), str(d.get("nouveau") or ""),
                                             str(d.get("confirmation") or ""))
    if ok:
        current_app.secret_key = auth.cle_secrete()   # nouvelle clé : les anciens cookies ne valent plus rien
        session["connecte"] = auth.identifiant()       # celui-ci est re-signé avec la nouvelle clé
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/statut")
def statut():
    d = request.get_json(force=True)
    if d.get("statut") not in STATUTS:
        return jsonify(ok=False, message="Statut inconnu."), 400
    champs = {"Statut": d["statut"]}
    email = str(d.get("email") or "").strip()
    if email:   # candidature « adresse à trouver » envoyée : adresse notée pour le suivi des réponses et la relance
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", email):
            return jsonify(ok=False, message=f"Adresse mail invalide : {email}"), 400
        champs["Email"] = email
    if d["statut"].startswith("Candidaté") and d.get("postule"):
        champs.update({"Date envoi": date.today(), "Dernière action": date.today()})
        if d["statut"] == "Candidaté (mail)":  # candidature par mail marquée envoyée : relance prévue comme pour un envoi détecté
            from jours import date_relance
            champs["Relance prévue"] = date_relance(date.today())
    ok, message = suivi_donnees.modifier(int(d["ligne"]), d["entreprise"], champs)
    if ok and d["statut"] == "Abandonné" and d.get("brouillon_a"):
        message += " " + lettres.supprimer_brouillons(d["brouillon_a"])
    return jsonify(ok=ok, message=message)


@api.post("/suivi/ajouter")
def ajouter_au_suivi():
    """Formulaire « Ajouter une candidature » de la page Suivi."""
    d = request.get_json(force=True, silent=True) or {}
    ok, message, doublon = suivi_donnees.ajouter(d)
    return jsonify(ok=ok, message=message, doublon=doublon), (200 if ok else 400)


@api.post("/suivi/fiche")
def fiche_entreprise():
    """Fiche d'une entreprise modifiée depuis la page Suivi (bouton ✏️)."""
    import fiche
    d = request.get_json(force=True, silent=True) or {}
    try:
        n = int(d.get("ligne"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Ligne invalide."), 400
    ok, message = fiche.modifier(n, str(d.get("entreprise") or ""), d.get("champs") or {})
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/ecrire")
def ecrire():
    """« Écrire ce qui manque » : lettre et réponses d'une candidature par formulaire, rédigées par le modèle."""
    import redaction
    d = request.get_json(force=True, silent=True) or {}
    try:
        ligne = int(d.get("ligne"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Ligne invalide."), 400
    ok, message = redaction.ecrire_ce_qui_manque(ligne, str(d.get("entreprise") or ""))
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/vers_lba")
def vers_lba():
    """« Postuler par La Bonne Alternance » : candidature « adresse à trouver » repassée par le formulaire du site."""
    import vers_lba as module
    d = request.get_json(force=True, silent=True) or {}
    try:
        ligne = int(d.get("ligne"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Ligne invalide."), 400
    ok, message = module.passer_par_lba(ligne, str(d.get("entreprise") or ""))
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/formulaire")
def formulaire():
    """« Ouvrir le formulaire prérempli » : formulaire La Bonne Alternance rempli dans Chrome (jamais envoyé) ;
    Chrome absent : renvoie les navigateurs installés, la page redemande avec celui choisi."""
    import formulaire_web
    d = request.get_json(force=True, silent=True) or {}
    try:
        ligne = int(d.get("ligne"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Ligne invalide."), 400
    from chrome import navigateurs
    navigateur = str(d.get("navigateur") or "") or None   # choisi dans la page quand Chrome est absent
    if navigateur and navigateur != navigateurs.DEFAUT and navigateur not in navigateurs.NAVIGATEURS:
        return jsonify(ok=False, message="Navigateur inconnu."), 400
    ok, message, extra = formulaire_web.ouvrir_formulaire(ligne, str(d.get("entreprise") or ""), request.host,
                                                          navigateur)
    if extra.get("navigateurs"):                            # Chrome absent : la page demande lequel
        return jsonify(ok=False, message=message, **extra)
    return jsonify(ok=ok, message=message, **extra), (200 if ok else 400)


@api.post("/extension_installer")
def extension_installer():
    """Aide à l'installation de l'extension : ouvre son dossier et la page des extensions de Chrome
    (Chrome absent : du navigateur par défaut s'il est bâti sur Chromium, Opera GX, Edge…)."""
    import subprocess
    import chrome
    import extension_lba
    from chrome import navigateurs
    dossier = extension_lba.dossier_extension()
    exe, nom, page = chrome.trouver_chrome(), "Chrome", "chrome://extensions"
    if not exe:
        cle = navigateurs.pour_extension()
        if not cle:
            return jsonify(ok=False, message="Ni Chrome ni Edge, Brave, Opera… sur ce PC : l'extension ne peut pas "
                                             "être installée."), 400
        exe, nom, page = navigateurs.chemin(cle), navigateurs.nom(cle), navigateurs.page_extensions(cle)
    subprocess.Popen([str(exe), page], close_fds=True)
    return jsonify(ok=True, dossier=str(dossier),
                   message=f"Page des extensions ouverte dans {nom}, chemin du dossier copié : active « Mode développeur », "
                           "clique « Charger l'extension non empaquetée », colle le chemin (Ctrl+V) et valide.")


@api.post("/extension_presente")
def extension_presente():
    """L'extension Chrome se signale (installée, Chrome démarré) : aucune donnée échangée, origine vérifiée."""
    import extension_lba
    ok = extension_lba.noter_presence(request.headers.get("Origin"))
    return jsonify(ok=ok), (200 if ok else 404)


@api.post("/extension_fiche")
def extension_fiche():
    """Formulaire ouvert hors de LMAgent : données pour l'extension Chrome de LMAgent seulement (origine vérifiée ;
    adresse de la fiche donnée par Chrome lui-même, voir extension_lba.donnees_fiche)."""
    import extension_lba
    d = request.get_json(force=True, silent=True) or {}
    donnees = extension_lba.donnees_fiche(str(d.get("url") or ""), request.headers.get("Origin"))
    r = jsonify(ok=donnees is not None, donnees=donnees)
    r.headers["Cache-Control"] = "no-store"
    return r, (200 if donnees is not None else 404)


@api.post("/extension/<jeton>")
def extension(jeton):
    """Données d'un formulaire prérempli, pour l'extension Chrome de LMAgent seulement (jeton à usage unique,
    origine de l'extension vérifiée ; pas de session ni de jeton d'interface : voir extension_lba.py)."""
    import extension_lba
    donnees = extension_lba.retirer(jeton, request.headers.get("Origin"))
    r = jsonify(ok=donnees is not None, donnees=donnees)
    r.headers["Cache-Control"] = "no-store"
    return r, (200 if donnees is not None else 404)


@api.post("/ecartee")
def ecartee():
    """Décision sur une entreprise écartée : candidater (quand même), abandonner, remettre."""
    import ecartees
    d = request.get_json(force=True, silent=True) or {}
    action = ecartees.ACTIONS.get(d.get("action"))
    if action is None:
        return jsonify(ok=False, message="Action inconnue."), 400
    ok, message = action(str(d.get("cle") or ""))
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/signature")
def signature():
    import parametres
    d = request.get_json(force=True)
    if not isinstance(d.get("signature"), dict):
        return jsonify(ok=False, message="Données invalides."), 400
    ok, message = parametres.enregistrer(d["signature"], d.get("debut"), d.get("ajouter"))
    return jsonify(ok=ok, message=message)


@api.post("/profil")
def profil():
    import parametres
    d = request.get_json(force=True, silent=True) or {}
    if not isinstance(d.get("texte"), str):
        return jsonify(ok=False, message="Données invalides."), 400
    ok, message = parametres.enregistrer_profil(d["texte"])
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.post("/interdits")
def interdits():
    import parametres
    d = request.get_json(force=True)
    if not isinstance(d.get("texte"), str):
        return jsonify(ok=False, message="Données invalides."), 400
    ok, message = parametres.enregistrer_interdits(d["texte"])
    return jsonify(ok=ok, message=message)


@api.post("/reglages")
def enregistrer_reglages():
    import reglages_web
    d = request.get_json(force=True)
    if not isinstance(d.get("valeurs"), dict):
        return jsonify(ok=False, message="Données invalides."), 400
    ok, message = reglages_web.enregistrer(d["valeurs"])
    return jsonify(ok=ok, message=message)


@api.post("/mise_a_jour")
def mise_a_jour_maintenant():
    """Vérifie tout de suite ; si une version plus récente s'installe, l'interface se ferme puis redémarre."""
    import emplacements
    import mise_a_jour
    if not emplacements.INSTALLEE and routines.en_cours():     # git pull sous une routine en cours : non
        return jsonify(ok=False, message="Une routine est en cours : attends qu'elle se termine pour mettre à jour.")
    lancee, message = mise_a_jour.verifier()
    if lancee:
        threading.Timer(1.0, icone_tache.quitter).start()
    return jsonify(ok=True, message=message, redemarrage=lancee)


@api.post("/quitter")
def quitter():
    """Arrête l'interface (le serveur web). Une routine lancée continue jusqu'au bout."""
    continue_routine = routines.en_cours()
    import veille_tour
    veille_tour.ARRET.update(lignes=[], fini=False)      # nouveau journal de fermeture, lu par la page
    # laisse le temps d'envoyer la réponse ; quitté par l'utilisateur : la tour est remise en veille
    threading.Timer(0.5, icone_tache.quitter, kwargs={"par_l_utilisateur": True}).start()
    return jsonify(ok=True, routine=continue_routine)


@api.get("/arret")
def arret():
    """Journal de la fermeture en cours (LM Studio fermé sur la tour, mise en veille), affiché par la page."""
    import veille_tour
    return jsonify(lignes=veille_tour.ARRET["lignes"], fini=veille_tour.ARRET["fini"])


@api.post("/annuler_routine")
def annuler_routine():
    """Bouton « Annuler » de la page Routines."""
    ok, message = routines.annuler()
    return jsonify(ok=ok, message=message), (200 if ok else 409)


@api.post("/routine/<nom>")
def lancer_routine(nom):
    if nom not in routines.SCRIPTS:
        abort(404)
    if routines.en_cours():
        return jsonify(ok=False, message=f"« {routines.ROUTINE['nom']} » tourne déjà."), 409
    donnees = request.get_json(silent=True, force=True) or {}
    try:
        fois = int(donnees.get("fois") or 1)
    except (TypeError, ValueError):
        fois = 1
    try:   # mails envoyés et reçus lus à partir de ce jour (vide : fenêtre habituelle)
        depuis = date.fromisoformat(donnees["depuis"]) if donnees.get("depuis") else None
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Date « depuis » invalide."), 400
    routines.lancer(nom, bool(donnees.get("essai")), fois, depuis)
    return jsonify(ok=True)


@api.get("/planification")
def liste_planification():
    import planification
    return jsonify(planification.taches())


@api.post("/planification")
def planifier():
    """{"nom": "relances", "heure": "10:00", "fois": 2} ajoute un passage programmé (même routine et même heure :
    remplacé) ; {"supprimer": "LMAgent_relances_1000"} en supprime un."""
    import planification
    d = request.get_json(force=True, silent=True) or {}
    if d.get("supprimer"):
        ok, message = planification.supprimer(str(d["supprimer"]))
    else:
        ok, message = planification.planifier(str(d.get("nom") or ""), str(d.get("heure") or "").strip(),
                                              d.get("fois") or 1)
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@api.get("/routine")
def etat_routine():
    return jsonify(routines.etat())


@api.get("/historique/<nom>")
def historique(nom):
    f = routines.fichier_du_journal(nom, prefixe="web_")
    if not f:
        abort(404)
    return jsonify(sortie=routines.fin_de_fichier(f, 400))


@api.get("/tour")
def etat_tour():
    if not tour_web.disponible():
        abort(404)
    return jsonify(etat=tour_web.etat(), action=tour_web.ETAT["action"], messages=tour_web.ETAT["messages"][-30:])


@api.post("/tour/<nom>")
def action_tour(nom):
    if not tour_web.disponible() or nom not in tour_web.ACTIONS:
        abort(404)
    ok, message = tour_web.lancer_action(nom)
    return jsonify(ok=ok, message=message), (200 if ok else 409)
