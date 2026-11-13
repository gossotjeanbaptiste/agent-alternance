"""Les pages de l'interface (affichage)."""
from datetime import date

from flask import Blueprint, abort, render_template, request

import lettres
from tableau import A_POSTULER
import relations
import routines
import suivi_donnees
import tour_web
from chemins import LOGS

pages = Blueprint("pages", __name__)


@pages.route("/")
def accueil():
    lignes = suivi_donnees.lire()
    return render_template("accueil.html", page="accueil", s=suivi_donnees.statistiques(lignes),
                           routine=routines.ROUTINE["nom"] if routines.en_cours() else None)


@pages.route("/suivi")
def suivi():
    lignes = suivi_donnees.lire()
    lignes.sort(key=lambda l: (l.get("Date envoi") or l.get("Date ajout") or date.min), reverse=True)
    return render_template("suivi.html", page="suivi", lignes=lignes)


@pages.route("/postuler")
def postuler():
    # formulaires d'abord, puis les candidatures par mail (brouillons à envoyer)
    a_faire = [l for l in suivi_donnees.lire() if l.get("Statut") in A_POSTULER or l.get("Statut") == "Brouillon"]
    a_faire.sort(key=lambda l: l.get("Statut") == "Brouillon")
    erreur = lettres.ajouter_lettres(a_faire)
    from messagerie import nom_messagerie
    return render_template("postuler.html", page="postuler", lignes=a_faire, erreur=erreur,
                           messagerie=nom_messagerie())


@pages.route("/routines")
def page_routines():
    return render_template("routines.html", page="routines", historique=routines.historique())


@pages.route("/tour")
def tour():
    if not tour_web.disponible():
        abort(404)
    return render_template("tour.html", page="tour")


@pages.route("/linkedin")
def linkedin():
    rel = relations.lire_relations()
    trouves = relations.correspondances(suivi_donnees.lire(), rel) if rel else []
    return render_template("linkedin.html", page="linkedin", trouves=trouves, total=len(rel) if rel else None)


@pages.route("/journal")
def journal():
    fichiers = sorted(LOGS.glob("*.log"), reverse=True) if LOGS.exists() else []
    choisi = request.args.get("f") or (fichiers[0].name if fichiers else None)
    f = routines.fichier_du_journal(choisi) if choisi else None
    return render_template("journal.html", page="journal", fichiers=[x.name for x in fichiers],
                           choisi=choisi, contenu=routines.fin_de_fichier(f, 400) if f else "")
