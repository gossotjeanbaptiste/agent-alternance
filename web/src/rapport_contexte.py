"""Données données au modèle pour rédiger le rapport : profil, bilan chiffré, réponses, relances, à postuler,
activité des routines. Listes plafonnées pour tenir dans la mémoire du modèle (~9B, contexte limité)."""
from suivi_donnees import EN_ATTENTE
from tableau import PAGE_A_POSTULER

MAX_LIGNES = 30          # entreprises par liste
MAX_PROFIL = 1500        # caractères du profil
MAX_REPONSE = 250        # caractères de chaque « Dernière réponse »


def _d(x):
    return f"{x:%d/%m/%Y}" if x else "?"


def _profil():
    try:
        import commun
        return commun.PROFIL.strip()[:MAX_PROFIL]
    except Exception:
        return ""


def _journal(j):
    routines = ", ".join(f"{k} : {n}" for k, n in j["routines"].most_common()) or "aucune"
    reponses = ", ".join(f"{k} : {n}" for k, n in j["reponses"].most_common()) or "aucune"
    lignes = [f"Journaux lus : {j['jours']} jour(s)",
              f"Routines terminées : {sum(j['routines'].values())} ({routines}), {j['minutes']} min au total",
              f"Brouillons de candidature : {j['candidatures']} ; lettres prêtes pour un formulaire : {j['lettres']} ; "
              f"relances préparées : {j['relances_brouillon']}",
              f"Envois repérés dans la messagerie : {j['envois_vus']} ; relances envoyées repérées : {j['relances_vues']}",
              f"Réponses lues et classées par le modèle : {reponses}"]
    if j["problemes"]:
        lignes.append("Problèmes notés : " + " | ".join(j["problemes"][:6]))
    return lignes


def contexte(r):
    """Le bloc de données (texte) donné au modèle."""
    import rapport
    t, lignes = r["t"], r.get("lignes") or []
    blocs = [f"Période du rapport : du {_d(r['debut'])} au {_d(r['fin'])} (rapport fait le {_d(r['genere'])}).",
             "", "--- Profil de l'étudiant ---", _profil() or "(non renseigné)",
             "", "--- Bilan chiffré (tableau de suivi) ---", rapport.texte(r)]
    if t["liste_reponses"]:
        blocs += ["", "--- Contenu des réponses reçues sur la période ---"]
        for l in t["liste_reponses"][:MAX_LIGNES]:
            blocs.append(f"- {l.get('Entreprise') or '?'} ({l.get('Statut')}) : "
                         f"{str(l.get('Dernière réponse') or '(pas de résumé)')[:MAX_REPONSE]}")
    attente = sorted((l for l in lignes if l.get("Statut") in EN_ATTENTE and l.get("Date envoi")),
                     key=lambda l: l["Date envoi"])
    if attente:
        blocs += ["", f"--- Candidatures toujours sans réponse ({len(attente)}, les plus anciennes d'abord) ---"]
        blocs += [f"- {l.get('Entreprise')} : envoyée le {_d(l['Date envoi'])}, {l.get('Statut')}, "
                  f"{l.get('Nb relances') or 0} relance(s)" for l in attente[:MAX_LIGNES]]
    if t["relances"]:
        blocs += ["", "--- Relances prévues dans les 14 prochains jours ---"]
        blocs += [f"- {_d(l['Relance prévue'])} : {l.get('Entreprise')}" for l in t["relances"][:MAX_LIGNES]]
    a_postuler = [l for l in lignes if l.get("Statut") in PAGE_A_POSTULER]
    if a_postuler:
        blocs += ["", f"--- Candidatures prêtes, à finaliser par l'étudiant ({len(a_postuler)}) ---"]
        blocs += [f"- {l.get('Entreprise')} : {l.get('Statut')}" for l in a_postuler[:MAX_LIGNES]]
    blocs += ["", "--- Activité des routines automatiques (journaux) ---"] + _journal(r["j"])
    blocs.append(f"Nouvelles entreprises écartées par le filtre d'activité (hors informatique) : {r['ecartees']}")
    return "\n".join(blocs)
