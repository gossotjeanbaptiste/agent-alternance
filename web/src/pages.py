"""Les pages de l'interface (affichage)."""
from datetime import date

from flask import Blueprint, abort, redirect, render_template, request

import lettres
from tableau import ADRESSE_A_TROUVER, PAGE_A_POSTULER
import relations
import routines
import suivi_donnees
import tour_web
from chemins import LOGS

pages = Blueprint("pages", __name__)


@pages.route("/assistant")
def assistant():
    """Assistant de premier lancement (aussi accessible ensuite pour tout revoir)."""
    import assistant as a
    import reglages_web  # noqa: F401
    return render_template("assistant.html", page="assistant", e=a.etat(), a_faire=a.a_faire())


@pages.route("/connexion")
def connexion():
    """Création du compte au premier lancement, sinon connexion."""
    import auth
    import securite
    suite = securite.suite_sure(request.args.get("suite"))
    if securite.connecte():
        return redirect(suite)
    return render_template("connexion.html", creation=not auth.compte_existe(), identifiant=auth.identifiant(),
                           longueur_min=auth.LONGUEUR_MIN, suite=suite)


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


@pages.route("/rapport")
def page_rapport():
    import rapport
    import rapport_ia
    import rapport_md
    r = rapport.generer(request.args)
    enregistres = rapport_ia.enregistres()
    ia = request.args.get("ia") or (enregistres[0] if enregistres else "")
    ia_texte = rapport_ia.lire(ia)
    return render_template("rapport.html", page="rapport", r=r, periodes=rapport.PERIODES, texte=rapport.texte(r),
                           enregistres=enregistres, ia=ia if ia_texte else "", ia_texte=ia_texte,
                           ia_html=rapport_md.en_html(ia_texte), ia_etat=rapport_ia.ETAT)


@pages.route("/parametres")
def page_parametres():
    import parametres
    import reglages_web
    signature, debut = parametres.lire()
    ajouter, fichier = parametres.ajouter_signature()
    return render_template("parametres.html", page="parametres", champs=parametres.CHAMPS,
                           signature=signature, debut=debut, ajouter=ajouter, fichier=fichier,
                           interdits=parametres.lire_interdits(), profil=parametres.lire_profil(),
                           version=__import__("version").__version__, installee=__import__("emplacements").INSTALLEE,
                           sections=reglages_web.sections())


@pages.route("/postuler")
def postuler():
    # formulaires d'abord, puis les candidatures par mail (brouillons à envoyer), puis les adresses à trouver
    ordre = {"Brouillon": 1, ADRESSE_A_TROUVER: 2}
    a_faire = [l for l in suivi_donnees.lire() if l.get("Statut") in PAGE_A_POSTULER]
    a_faire.sort(key=lambda l: ordre.get(l.get("Statut"), 0))
    if request.args.get("frais"):       # bouton « 🔄 Recharger » : lettres relues dans la messagerie
        lettres.CACHE["quand"] = 0
    erreur = lettres.ajouter_lettres(a_faire)
    from messagerie import nom_messagerie
    import extension_lba
    return render_template("postuler.html", page="postuler", lignes=a_faire, erreur=erreur,
                           messagerie=nom_messagerie(), extension=extension_lba.etat())


@pages.route("/ecartees")
def ecartees():
    import ecartees as e
    return render_template("ecartees.html", page="ecartees", g=e.lire())


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
