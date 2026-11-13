"""Met à jour le tableau de suivi en comparant avec Outlook (brouillons et mails envoyés),
puis te demande ce que tu as fait pour tout ce qu'il ne peut pas deviner.

    python alternance\\maj_tableau.py            -> mise à jour avec questions
    python alternance\\maj_tableau.py --voir     -> affiche seulement l'état, ne modifie rien

Pas besoin du modèle IA : c'est instantané. Ferme le tableau Excel avant de lancer.
Tape Entrée pour passer une question (rien n'est changé pour cette ligne).
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # modules internes (alternance/src)
import commun  # noqa: E402
from commun import CFG, P  # noqa: E402
from jours import date_relance  # noqa: E402
from mails import est_adresse  # noqa: E402
from messagerie import nom_messagerie, ouvrir  # noqa: E402
from tableau import A_POSTULER, MAIL, Suivi, as_date, statut_par_canal  # noqa: E402

VOIR = False
A_SUPPRIMER = []


def demander(question, choix):
    """choix : {"1": "libellé", ...}. Renvoie la clé choisie, ou "" pour passer."""
    if VOIR:
        return ""
    print(f"\n   {question}")
    print("     0. Rien fait pour l'instant (la ligne reste telle quelle)")
    for k, v in choix.items():
        print(f"     {k}. {v}")
    while True:
        r = input("   Ton choix (0 ou Entrée = rien fait) > ").strip().lower()
        if r in ("", "0"):
            return ""
        if r in choix:
            return r
        print("   Réponse non reconnue.")


def demander_date(defaut=None):
    defaut = defaut or date.today()
    r = input(f"   Date (jj/mm, Entrée = {defaut:%d/%m}) > ").strip()
    if not r:
        return defaut
    try:
        j, m = map(int, r.replace("-", "/").split("/")[:2])
        d = date(date.today().year, m, j)
        return d if d <= date.today() else date(d.year - 1, m, j)
    except Exception:
        print("   Date illisible, je prends", f"{defaut:%d/%m}")
        return defaut


def titre(s, row):
    ent = s.get(row, "Entreprise")
    poste = s.get(row, "Poste") or ""
    mail = s.get(row, "Email") or "pas d'adresse"
    print(f"\n── {ent} — {poste[:50]} ({mail})")


def main():
    global VOIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--voir", action="store_true", help="affiche l'état sans rien modifier")
    VOIR = ap.parse_args().voir
    if VOIR:
        commun.ESSAI = True  # empêche toute sauvegarde

    print(f"📬 Lecture de {nom_messagerie()} (brouillons et mails envoyés)...")
    s = Suivi(P(CFG["tableau_suivi"]))
    ol = ouvrir()
    envois = ol.envois(120)
    brouillons = ol.destinataires_brouillons()
    programmes = ol.programmes()  # envois planifiés par toi, en attente de leur heure
    stats = {"auto": 0, "réponses": 0, "attente": 0, "passées": 0}

    for row in list(s.rows()):
        statut = s.get(row, "Statut") or ""
        mail = str(s.get(row, "Email") or "").strip().lower()
        a_adresse = est_adresse(mail)
        mes_envois = sorted(envois.get(mail, []), key=lambda x: x[0]) if a_adresse else []
        derniere = as_date(s.get(row, "Dernière action")) or as_date(s.get(row, "Date envoi"))
        ent = s.get(row, "Entreprise")

        # ---------- candidature en brouillon (avec adresse)
        if statut in ("Brouillon", "Brouillon (adresse à trouver)") and a_adresse:
            if mes_envois:
                d = mes_envois[0][0].date()
                s.set(row, "Statut", MAIL)
                s.set(row, "Date envoi", d)
                s.set(row, "Dernière action", d)
                s.set(row, "Relance prévue", date_relance(d))
                print(f"✅ {ent} : envoyé le {d:%d/%m} (trouvé dans Éléments envoyés)")
                stats["auto"] += 1
                continue
            if mail in programmes:
                print(f"⏰ {ent} : candidature dans la Boîte d'envoi, envoi programmé")
                stats["attente"] += 1
                continue
            if mail in brouillons:
                stats["attente"] += 1
                continue  # le brouillon attend toujours dans Outlook : rien à demander
            titre(s, row)
            r = demander("Le brouillon n'est plus dans Outlook et aucun envoi n'est trouvé. Qu'as-tu fait ?", {
                "1": "Envoyé par mail (depuis une autre boîte, ou je l'ai réécrit)",
                "2": "Postulé autrement (site, formulaire, La Bonne Alternance, LinkedIn...)",
                "3": "Abandonné, je ne postule pas",
                "4": "Retirer du tableau (la recherche pourra la reproposer)"})
            appliquer_candidature(s, row, r, stats)

        # ---------- candidature sans adresse / à faire sur La Bonne Alternance
        elif statut in ("Brouillon (adresse à trouver)", "Brouillon", *A_POSTULER):
            titre(s, row)
            if s.get(row, "Lien"):
                print(f"   Lien : {s.get(row, 'Lien')}")
            r = demander("Où en est cette candidature ?", {
                "1": "Envoyée par mail (je saisis l'adresse)",
                "2": "Postulé sur le site / La Bonne Alternance / autre canal",
                "3": "Abandonné, je ne postule pas",
                "4": "Retirer du tableau (la recherche pourra la reproposer)",
                "5": "J'ai trouvé l'adresse mais pas encore envoyé"})
            if r in ("1", "5"):
                adr = input("   Adresse mail > ").strip().lower()
                if est_adresse(adr):
                    s.set(row, "Email", adr)
                    if r == "5":
                        s.set(row, "Statut", "Brouillon")
                        print("   Adresse enregistrée. Mets-la dans le brouillon Outlook puis envoie-le.")
                        continue
                else:
                    print("   Adresse invalide, ligne inchangée.")
                    stats["passées"] += 1
                    continue
            appliquer_candidature(s, row, r if r != "5" else "", stats)

        # ---------- relance en brouillon
        elif statut in ("Relance en brouillon", "Relance programmée"):
            if mes_envois and derniere and mes_envois[-1][0].date() > derniere:
                d = mes_envois[-1][0].date()
                nb = int(s.get(row, "Nb relances") or 0)
                s.set(row, "Statut", "Relancé")
                s.set(row, "Dernière action", d)
                s.set(row, "Relance prévue", date_relance(d) if nb < CFG["relances_max"] else None)
                print(f"✅ {ent} : relance envoyée le {d:%d/%m} (trouvée dans Éléments envoyés)")
                stats["auto"] += 1
                continue
            if mail in programmes:
                q = programmes[mail]
                s.set(row, "Statut", "Relance programmée")
                print(f"⏰ {ent} : relance programmée{f' pour le {q:%d/%m à %H:%M}' if q else ''}")
                stats["attente"] += 1
                if not VOIR:
                    s.save()
                continue
            if mail in brouillons:
                stats["attente"] += 1
                continue
            titre(s, row)
            r = demander("Le brouillon de relance n'est plus dans Outlook et aucun envoi n'est trouvé. Qu'as-tu fait ?", {
                "1": "Relance envoyée (autrement, ou réécrite à la main)",
                "2": "Supprimée : la refaire au prochain lancement de relances.py",
                "3": "Ne plus relancer cette entreprise"})
            nb = int(s.get(row, "Nb relances") or 0)
            if r == "1":
                d = demander_date()
                s.set(row, "Statut", "Relancé")
                s.set(row, "Dernière action", d)
                s.set(row, "Relance prévue", date_relance(d) if nb < CFG["relances_max"] else None)
            elif r == "2":
                nb = max(0, nb - 1)
                s.set(row, "Nb relances", nb)
                s.set(row, "Statut", "Relancé" if nb else MAIL)
            elif r == "3":
                s.set(row, "Statut", "Sans réponse")
                s.set(row, "Relance prévue", None)
            else:
                stats["passées"] += 1
                continue
            stats["réponses"] += 1

        # ---------- réponse à lire
        elif statut == "Réponse à lire":
            titre(s, row)
            print(f"   Réponse : {s.get(row, 'Dernière réponse') or '(pas de résumé)'}")
            r = demander("C'était quoi, cette réponse ?", {
                "1": "Entretien proposé", "2": "Réponse positive", "3": "Refus",
                "4": "Accepté !", "5": "Rien de décisif : continuer le suivi (relances)"})
            nouveaux = {"1": "Entretien", "2": "Réponse positive", "3": "Refus", "4": "Accepté"}
            if r in nouveaux:
                s.set(row, "Statut", nouveaux[r])
                s.set(row, "Relance prévue", None)
            elif r == "5":
                s.set(row, "Statut", MAIL if not int(s.get(row, "Nb relances") or 0) else "Relancé")
                base = as_date(s.get(row, "Dernière action")) or date.today()
                s.set(row, "Relance prévue", date_relance(max(base, date.today())))
            else:
                stats["passées"] += 1
                continue
            stats["réponses"] += 1
        else:
            continue
        if not VOIR:
            s.save()  # sauvegarde après chaque réponse : rien n'est perdu si tu quittes en cours

    for n in sorted(A_SUPPRIMER, reverse=True):
        s.ws.delete_rows(n)
    s.save()
    print(f"\n📊 {stats['auto']} mise(s) à jour automatique(s), {stats['réponses']} réponse(s) enregistrée(s), "
          f"{stats['attente']} brouillon(s) toujours en attente dans Outlook, {stats['passées']} passée(s).")
    if VOIR:
        print("   (mode --voir : rien n'a été modifié)")


def appliquer_candidature(s, row, r, stats):
    if r == "1":
        d = demander_date()
        s.set(row, "Statut", MAIL)
        s.set(row, "Date envoi", d)
        s.set(row, "Dernière action", d)
        s.set(row, "Relance prévue", date_relance(d))
    elif r == "2":
        canal = input("   Par quel canal ? (La Bonne Alternance / formulaire du site / LinkedIn / autre, "
                      "Entrée = La Bonne Alternance) > ").strip() or "La Bonne Alternance"
        d = demander_date()
        s.set(row, "Statut", statut_par_canal(canal))
        s.set(row, "Date envoi", d)
        s.set(row, "Dernière action", d)
        s.set(row, "Notes", f"Candidature via : {canal}. {s.get(row, 'Notes') or ''}".strip())
    elif r == "3":
        s.set(row, "Statut", "Abandonné")
        s.set(row, "Relance prévue", None)
    elif r == "4":
        A_SUPPRIMER.append(row[0].row)  # supprimée à la fin (supprimer en cours décalerait les lignes)
        print("   Ligne retirée (à l'enregistrement final).")
    else:
        stats["passées"] += 1
        return
    stats["réponses"] += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu : les réponses déjà données sont enregistrées.")
