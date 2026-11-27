"""Ce que la messagerie dit des envois d'une candidature : premier mail envoyé, relance envoyée, relance programmée,
brouillon de relance disparu (supposé programmé, ou supprimé : relance à recréer)."""
from commun import CFG, say
from jours import date_relance
from tableau import MAIL


def _envoi_constate(p, l):
    s = p.suivi
    premier, dernier = l.mes_envois[0][0], l.mes_envois[-1][0]
    if l.statut == "Brouillon":
        s.set(l.row, "Statut", MAIL)
        s.set(l.row, "Date envoi", premier.date())
        s.set(l.row, "Dernière action", premier.date())
        s.set(l.row, "Relance prévue", date_relance(premier.date()))
        l.statut, l.derniere = MAIL, premier.date()
        say(f"   ✉️  {l.ent} : envoyé le {premier:%d/%m}")
        p.bilan["envoi(s) repéré(s)"] += 1
    elif l.statut in ("Relance en brouillon", "Relance programmée") and l.derniere and dernier.date() > l.derniere:
        nb = int(s.get(l.row, "Nb relances") or 0)
        s.set(l.row, "Statut", "Relancé")
        s.set(l.row, "Dernière action", dernier.date())
        s.set(l.row, "Relance prévue", date_relance(dernier.date()) if nb < CFG["relances_max"] else None)
        l.statut, l.derniere = "Relancé", dernier.date()
        say(f"   🔁 {l.ent} : relance envoyée le {dernier:%d/%m}")
        p.bilan["relance(s) envoyée(s) repérée(s)"] += 1


def _brouillon_de_relance(p, l):
    s, ol = p.suivi, p.ol
    mails = l.mails or [l.mail]          # toutes les adresses de la candidature
    programmee = next((a for a in mails if a in p.programmes), None)
    en_brouillon = any(a in p.brouillons for a in mails)
    # relance planifiée par toi (nouvel Outlook : reste dans Brouillons) ou dans la Boîte d'envoi
    if l.statut == "Relance en brouillon" and programmee:
        l.statut = "Relance programmée"
        s.set(l.row, "Statut", l.statut)
        q = p.programmes[programmee]
        say(f"   ⏰ {l.ent} : relance programmée{f' pour le {q:%d/%m à %H:%M}' if q else ''}")

    # brouillon de relance disparu sans envoi, avec une messagerie qui ne montre pas les envois
    # programmés (IMAP hors Gmail) : on suppose que tu l'as programmé, pas supprimé.
    # (Si tu l'as supprimé : python alternance\maj_tableau.py corrige la ligne.)
    if not ol.voit_programmes and l.statut == "Relance en brouillon" and not en_brouillon:
        l.statut = "Relance programmée"
        s.set(l.row, "Statut", l.statut)
        say(f"   ⏰ {l.ent} : brouillon de relance parti des Brouillons sans envoi visible : supposé programmé")

    # brouillon de relance supprimé sans être envoyé : on la remet dans la file pour la recréer
    if ol.voit_programmes and l.statut in ("Relance en brouillon", "Relance programmée") \
            and not en_brouillon and not programmee:
        nb = max(0, int(s.get(l.row, "Nb relances") or 0) - 1)
        l.statut = "Relancé" if nb else MAIL
        s.set(l.row, "Nb relances", nb)
        s.set(l.row, "Statut", l.statut)
        say(f"   ♻️  {l.ent} : brouillon de relance introuvable dans Outlook, il va être recréé")


def constater(p, l):
    if l.mes_envois:
        _envoi_constate(p, l)
    _brouillon_de_relance(p, l)
