"""Les actions de l'interface (appelées par le JavaScript des pages)."""
import os
import threading
from datetime import date

from flask import Blueprint, abort, jsonify, request

import lettres
import routines
import suivi_donnees
import tour_web
from tableau import STATUTS

api = Blueprint("api", __name__, url_prefix="/api")


@api.post("/statut")
def statut():
    d = request.get_json(force=True)
    if d.get("statut") not in STATUTS:
        return jsonify(ok=False, message="Statut inconnu."), 400
    champs = {"Statut": d["statut"]}
    if d["statut"].startswith("Candidaté") and d.get("postule"):
        champs.update({"Date envoi": date.today(), "Dernière action": date.today()})
    ok, message = suivi_donnees.modifier(int(d["ligne"]), d["entreprise"], champs)
    if ok and d["statut"] == "Abandonné" and d.get("brouillon_a"):
        message += " " + lettres.supprimer_brouillons(d["brouillon_a"])
    return jsonify(ok=ok, message=message)


@api.post("/signature")
def signature():
    import parametres
    d = request.get_json(force=True)
    if not isinstance(d.get("signature"), dict):
        return jsonify(ok=False, message="Données invalides."), 400
    ok, message = parametres.enregistrer(d["signature"], d.get("debut"), d.get("ajouter"))
    return jsonify(ok=ok, message=message)


@api.post("/quitter")
def quitter():
    """Arrête l'interface (le serveur web). Une routine lancée continue jusqu'au bout."""
    continue_routine = routines.en_cours()
    threading.Timer(0.5, lambda: os._exit(0)).start()  # laisse le temps d'envoyer la réponse
    return jsonify(ok=True, routine=continue_routine)


@api.post("/routine/<nom>")
def lancer_routine(nom):
    if nom not in routines.SCRIPTS:
        abort(404)
    if routines.en_cours():
        return jsonify(ok=False, message=f"« {routines.ROUTINE['nom']} » tourne déjà."), 409
    donnees = request.get_json(silent=True, force=True) or {}
    routines.lancer(nom, bool(donnees.get("essai")))
    return jsonify(ok=True)


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
