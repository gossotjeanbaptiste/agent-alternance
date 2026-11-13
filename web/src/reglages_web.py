"""Page Paramètres, partie « Tous les réglages » : affichage et enregistrement des réglages décrits
dans alternance/src/reglages.py (config_alternance.json et config.json).

Les routines relisent la config à chaque lancement : un changement compte dès la prochaine routine.
L'interface met à jour sa copie en mémoire ; quelques listes lues au démarrage (adresses, sites)
ne comptent pour l'interface qu'après l'avoir relancée.
"""
import json

import chemins  # noqa: F401
import commun
import lettres
import reglages
import emplacements
from chemins import ROOT

FICHIERS = {"alternance": lambda: commun.donnees.chemin("config_alternance.json"),
            "agent": lambda: emplacements.config_agent()}


def _lire(fichier):
    try:
        return json.loads(FICHIERS[fichier]().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _affichage(r, v):
    t = r["type"]
    if t == "liste":
        return "\n".join(str(x) for x in (v or []))
    if t == "json":
        return json.dumps(v, ensure_ascii=False, indent=1)
    if t == "secret":
        return ""
    if t == "oui_non":
        return bool(v)
    return "" if v is None else str(v)


def sections():
    """[(titre, [champ, …])] pour la page ; la section Tour n'apparaît que sur la branche avec la tour."""
    donnees = {f: _lire(f) for f in FICHIERS}
    import tour_web
    avec_tour = tour_web.tour is not None and commun.agent.utiliser_tour(donnees["agent"])
    res = {}
    for r in reglages.REGLAGES:
        if r["tour"] and not avec_tour:
            continue
        v = reglages.lire_chemin(donnees[r["fichier"]], r["chemin"], r["defaut"])
        if (r["fichier"], r["chemin"]) == ("agent", "utiliser_tour"):
            v = commun.agent.utiliser_tour(donnees["agent"])   # déduit des serveurs s'il n'est pas écrit
        res.setdefault(r["section"], []).append({
            **r, "cle": f"{r['fichier']}|{r['chemin']}", "valeur": _affichage(r, v),
            "defini": bool(v) if r["type"] == "secret" else True,
            "lignes": max(3, min(12, len(_affichage(r, v).splitlines()) + 1)) if r["type"] in ("liste", "json") else 0})
    return list(res.items())


def _convertir(r, brut, actuel):
    """Texte du formulaire -> valeur JSON ; lève ValueError avec un message clair."""
    t = r["type"]
    if t == "oui_non":
        return bool(brut)
    brut = "" if brut is None else str(brut)
    try:
        if t == "entier":
            return int(brut.strip())
        if t == "decimal":
            return float(brut.strip().replace(",", "."))
        if t == "liste":
            items = [l.strip() for l in brut.splitlines() if l.strip()]
            modele = actuel if isinstance(actuel, list) and actuel else r["defaut"]
            if modele and all(isinstance(x, int) for x in modele):  # ex. ports [9, 7]
                return [int(x) for x in items]
            return items
        if t == "json":
            return json.loads(brut)
    except json.JSONDecodeError as e:
        raise ValueError(f"format JSON invalide (ligne {e.lineno}, colonne {e.colno})")
    except ValueError:
        raise ValueError({"entier": "nombre entier attendu", "decimal": "nombre attendu (ex. 0,05)",
                          "liste": "une valeur par ligne, des nombres entiers ici"}.get(t, "valeur invalide"))
    if t == "choix" and r["choix"] and brut not in r["choix"]:
        raise ValueError(f"choisir parmi {', '.join(r['choix'])}")
    return brut.strip()


def enregistrer(valeurs):
    """valeurs : {"fichier|chemin": texte ou booléen}. Renvoie (ok, message)."""
    donnees = {f: _lire(f) for f in FICHIERS}
    erreurs, changes = [], {f: 0 for f in FICHIERS}
    for cle, brut in valeurs.items():
        fichier, _, chemin = cle.partition("|")
        r = reglages.PAR_CHEMIN.get((fichier, chemin))
        if not r:
            continue
        if r["type"] == "secret" and not str(brut or "").strip():
            continue  # vide : on garde le secret actuel
        actuel = reglages.lire_chemin(donnees[fichier], chemin)
        try:
            v = _convertir(r, brut, actuel)
        except (ValueError, TypeError) as e:
            erreurs.append(f"« {r['libelle']} » : {e}")
            continue
        if v != reglages.lire_chemin(donnees[fichier], chemin, r["defaut"]) or (actuel is None and v != r["defaut"]):
            reglages.ecrire_chemin(donnees[fichier], chemin, v)
            changes[fichier] += 1
    if erreurs:
        return False, "Rien n'est enregistré : " + " ; ".join(erreurs)
    for fichier, n in changes.items():
        if not n:
            continue
        try:
            FICHIERS[fichier]().write_text(json.dumps(donnees[fichier], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            return False, f"Écriture impossible : {e}"
    # copies en mémoire de l'interface
    if changes["alternance"]:
        commun.CFG.clear()
        commun.CFG.update(donnees["alternance"])
        lettres.CACHE["quand"] = 0
    if changes["agent"]:
        commun.agent.CONFIG.update(donnees["agent"])
    total = sum(changes.values())
    return True, (f"{total} réglage(s) enregistré(s). Les routines les prennent dès leur prochain lancement."
                  if total else "Aucun changement.")
