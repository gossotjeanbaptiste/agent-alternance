"""Bouton « ✍️ Écrire ce qui manque » de la page À postuler : la lettre et, pour le formulaire La Bonne Alternance,
les réponses aux trois questions, rédigées par le modèle (la tour, sinon ce PC) puis le modèle est déchargé."""
import threading

import chemins  # noqa: F401  (rend les modules d'alternance importables)
import commun
import routines
from tableau import A_POSTULER, Suivi

VERROU = threading.Lock()   # une seule rédaction à la fois (le modèle ne sert qu'une demande)


def manque(statut, lien, lettre_connue, deja):
    """[« la lettre », « les réponses »] : ce qu'il reste à écrire pour cette candidature."""
    import reponses
    a_faire = [] if lettre_connue else ["la lettre"]
    if reponses.questions_attendues(statut) and not reponses.a_des_reponses(deja.get(lien)):
        a_faire.append("les réponses")
    return a_faire


def ecrire_ce_qui_manque(n_ligne, entreprise):
    """Rédige ce qui manque pour la ligne n_ligne du tableau. Renvoie (ok, message)."""
    if routines.en_cours():
        return False, "Une routine est en cours (elle utilise le modèle) : attends qu'elle se termine."
    if not VERROU.acquire(blocking=False):
        return False, "Une rédaction est déjà en cours : attends qu'elle se termine."
    import agent
    import lettres
    import postuler
    import reponses
    try:
        s = Suivi(commun.chemin_tableau())
        row = next((r for r in s.rows() if r[0].row == n_ligne), None)
        if not row or str(s.get(row, "Entreprise")) != entreprise:
            return False, "Ligne introuvable (le tableau a changé) : recharge la page."
        statut, lien = s.get(row, "Statut"), (s.get(row, "Lien") or "").strip()
        if statut not in A_POSTULER or not lien:
            return False, "Seules les candidatures par formulaire (avec un lien pour postuler) sont concernées."
        lettre_connue = bool(lettres.lettres_et_signature()[0].get(lien))
        deja = reponses.lire()
        a_faire = manque(statut, lien, lettre_connue, deja)
        if not a_faire:
            return True, f"{entreprise} : rien ne manque."
        if "la lettre" in a_faire:
            postuler.ecrire_lettre(s, row)
        if "les réponses" in a_faire:
            postuler.reponses_de(s, row, deja)
        return True, f"{entreprise} : {' et '.join(a_faire)}, c'est écrit."
    except SystemExit:            # serveur du modèle injoignable (agent.ensure_server)
        return False, "Le modèle ne répond pas : vérifie LM Studio (sur la tour ou ce PC), puis réessaie."
    except Exception as e:
        return False, f"Rédaction impossible : {e}"
    finally:
        try:
            agent.liberer_modele()            # sinon le modèle resterait chargé tant que l'interface tourne
        except Exception:
            pass
        postuler.preparer_modele.pret = False
        lettres.CACHE["quand"] = 0            # la page relira les lettres
        VERROU.release()
