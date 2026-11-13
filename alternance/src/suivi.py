"""Mise à jour du suivi d'après la messagerie (envois, réponses, non-remises) et relances."""
import re
from collections import Counter
from datetime import date, datetime

import commun
from commun import CFG, PROFIL, say
from jours import date_relance, heure_aleatoire, prochain_ouvrable
from mails import DOMAINES_PERSO, domaine, est_adresse, est_generique, texte_vers_html
from modele import llm, llm_json
from messagerie import nom_messagerie, texte_mail, type_messagerie
from tableau import MAIL, as_date

def classer_reponse(entreprise, sujet, corps):
    try:
        r = llm_json(
            f"Un étudiant a candidaté pour une alternance chez « {entreprise} ». Voici une réponse reçue.\n"
            f"Sujet : {sujet}\n---\n{corps[:3000]}\n---\n"
            'Classe-la : {"type": "entretien" | "positive" | "refus" | "automatique" | "autre", '
            '"resume": "une phrase"}. "automatique" = accusé de réception automatique sans décision.')
        return r.get("type", "autre"), r.get("resume", "")
    except Exception as e:
        return "autre", f"(classement impossible : {e})"


def mettre_a_jour(suivi, ol):
    say(f"📬 Lecture de {nom_messagerie()}...")
    # on ne remonte pas plus loin que la plus ancienne candidature encore en cours
    actives = [as_date(suivi.get(r, "Date envoi")) or as_date(suivi.get(r, "Date ajout"))
               for r in suivi.rows()
               if (suivi.get(r, "Statut") or "").startswith(("Brouillon", "Candidaté (mail)", "Relance"))]
    actives = [d for d in actives if d]
    jours = min(120, max(15, (date.today() - min(actives)).days + 3)) if actives else 15
    envois = ol.envois(jours)
    recus = ol.recus(jours)
    brouillons = ol.destinataires_brouillons()
    programmes = ol.programmes()
    if commun.GARDE:  # Outlook a répondu : la suite (le modèle) peut prendre le temps qu'il faut
        commun.GARDE.cancel()
    ndr = [m for m in recus if "REPORT" in m["classe"].upper()
           or re.search(r"non remis|undeliverable|delivery has failed|échec de la remise|"
                        r"n'a pas pu être remis|could not be delivered", m["sujet"], re.I)]
    aujourd_hui = date.today()
    STATUTS_ACTIFS = {"Brouillon", MAIL, "Relance en brouillon", "Relance programmée", "Relancé"}
    a_relancer = []
    nb_domaines = Counter(domaine(str(suivi.get(r, "Email") or "").strip()) for r in suivi.rows())

    for row in suivi.rows():
        ent = suivi.get(row, "Entreprise")
        mail = (suivi.get(row, "Email") or "").strip().lower()
        statut = suivi.get(row, "Statut") or ""
        if statut.startswith("Brouillon") and mail:  # adresse ajoutée à la main depuis
            statut = "Brouillon"
        if not est_adresse(mail) or statut not in STATUTS_ACTIFS:
            continue  # « linkedin », « labonnealternance »... : pas une adresse, pas de suivi mail
        mes_envois = sorted(envois.get(mail, []), key=lambda x: x[0])
        derniere = as_date(suivi.get(row, "Dernière action"))

        # --- envoi constaté
        if mes_envois:
            premier, dernier = mes_envois[0][0], mes_envois[-1][0]
            if statut == "Brouillon":
                suivi.set(row, "Statut", MAIL)
                suivi.set(row, "Date envoi", premier.date())
                suivi.set(row, "Dernière action", premier.date())
                suivi.set(row, "Relance prévue", date_relance(premier.date()))
                statut, derniere = MAIL, premier.date()
                say(f"   ✉️  {ent} : envoyé le {premier:%d/%m}")
            elif statut in ("Relance en brouillon", "Relance programmée") and derniere \
                    and dernier.date() > derniere:
                nb = int(suivi.get(row, "Nb relances") or 0)
                suivi.set(row, "Statut", "Relancé")
                suivi.set(row, "Dernière action", dernier.date())
                suivi.set(row, "Relance prévue",
                          date_relance(dernier.date()) if nb < CFG["relances_max"] else None)
                statut, derniere = "Relancé", dernier.date()
                say(f"   🔁 {ent} : relance envoyée le {dernier:%d/%m}")

        # --- relance planifiée par toi (nouvel Outlook : reste dans Brouillons) ou dans la Boîte d'envoi
        if statut == "Relance en brouillon" and mail in programmes:
            statut = "Relance programmée"
            suivi.set(row, "Statut", statut)
            q = programmes[mail]
            say(f"   ⏰ {ent} : relance programmée{f' pour le {q:%d/%m à %H:%M}' if q else ''}")

        # --- brouillon de relance disparu sans envoi, avec une messagerie qui ne montre pas les envois
        # programmés (IMAP hors Gmail) : on suppose que tu l'as programmé, pas supprimé.
        # (Si tu l'as supprimé : python alternance\maj_tableau.py corrige la ligne.)
        if not ol.voit_programmes and statut == "Relance en brouillon" and mail not in brouillons:
            statut = "Relance programmée"
            suivi.set(row, "Statut", statut)
            say(f"   ⏰ {ent} : brouillon de relance parti des Brouillons sans envoi visible : supposé programmé")

        # --- brouillon de relance supprimé sans être envoyé : on la remet dans la file pour la recréer
        if ol.voit_programmes and statut in ("Relance en brouillon", "Relance programmée") \
                and mail not in brouillons and mail not in programmes:
            nb = max(0, int(suivi.get(row, "Nb relances") or 0) - 1)
            statut = "Relancé" if nb else MAIL
            suivi.set(row, "Nb relances", nb)
            suivi.set(row, "Statut", statut)
            say(f"   ♻️  {ent} : brouillon de relance introuvable dans Outlook, il va être recréé")

        if statut == "Brouillon":
            continue
        depuis = as_date(suivi.get(row, "Date envoi")) or aujourd_hui

        # --- adresse invalide
        if any(mail in (m["corps"] + m["sujet"]).lower() for m in ndr if m["date"].date() >= depuis):
            suivi.set(row, "Statut", "Adresse invalide")
            suivi.set(row, "Notes", f"Avis de non-remise reçu. {suivi.get(row, 'Notes') or ''}".strip())
            say(f"   ❌ {ent} : adresse {mail} invalide")
            continue

        # --- réponse reçue (même adresse, ou même domaine si ce n'est pas un domaine perso)
        dom = domaine(mail)
        # même domaine accepté seulement s'il est propre à cette entreprise dans le tableau
        # (ex. un domaine d'université présent sur 2 lignes -> adresse exacte uniquement)
        dom_ok = dom and dom not in DOMAINES_PERSO and dom not in CFG.get("domaines_ignores", []) and nb_domaines[dom] == 1
        reps = [m for m in recus if m["date"].date() >= depuis and est_adresse(m["de"]) and
                (m["de"] == mail or (dom_ok and domaine(m["de"]) == dom))]
        traitees = str(suivi.get(row, "Dernière réponse") or "")
        reps = [m for m in reps if f"{m['date']:%Y-%m-%d %H:%M}" not in traitees]
        for m in sorted(reps, key=lambda x: x["date"]):
            typ, resume = classer_reponse(ent, m["sujet"], m["corps"])
            suivi.set(row, "Dernière réponse", f"{m['date']:%Y-%m-%d %H:%M} [{typ}] {resume}")
            if typ != "automatique":
                suivi.set(row, "Statut", {"entretien": "Entretien", "positive": "Réponse positive",
                                          "refus": "Refus"}.get(typ, "Réponse à lire"))
                suivi.set(row, "Relance prévue", None)
                statut = "Réponse"
            say(f"   📩 {ent} : réponse [{typ}] {resume}")
        if statut == "Réponse":
            continue

        # --- relance due ?
        nb = int(suivi.get(row, "Nb relances") or 0)
        prevue = as_date(suivi.get(row, "Relance prévue"))
        if statut in (MAIL, "Relancé") and nb < CFG["relances_max"] and prevue \
                and prevue <= prochain_ouvrable(aujourd_hui, inclus=False):
            if mes_envois:
                a_relancer.append((row, mes_envois[-1]))
            else:  # mail d'origine pas dans « Éléments envoyés » (autre boîte, webmail...) : relance sans transfert
                d = as_date(suivi.get(row, "Date envoi")) or aujourd_hui
                a_relancer.append((row, (datetime(d.year, d.month, d.day), "", None)))
        elif statut == "Relancé" and nb >= CFG["relances_max"] and derniere \
                and date_relance(derniere) <= aujourd_hui:
            suivi.set(row, "Statut", "Sans réponse")
            say(f"   💤 {ent} : sans réponse après {nb} relance(s)")

    a_relancer.sort(key=lambda x: as_date(suivi.get(x[0], "Relance prévue")) or date.min)
    maxi = CFG.get("relances_max_par_jour", 5)
    if len(a_relancer) > maxi:
        say(f"   {len(a_relancer)} relances dues : {maxi} aujourd'hui, les autres les jours suivants")
    for row, (t, sujet, item) in a_relancer[:maxi]:
        preparer_relance(suivi, ol, row, t, sujet, item)


def preparer_relance(suivi, ol, row, t_envoi, sujet, item):
    ent, mail = suivi.get(row, "Entreprise"), suivi.get(row, "Email")
    contact = suivi.get(row, "Contact") or ""
    nb = int(suivi.get(row, "Nb relances") or 0) + 1
    prevue = as_date(suivi.get(row, "Relance prévue")) or date.today()
    jour = prevue if prevue > date.today() else prochain_ouvrable(date.today(), inclus=False)
    quand = heure_aleatoire(jour)
    formel = est_generique(mail) or not contact
    precedent = texte_mail(item)
    if precedent:
        consigne_ton = (
            "Voici le DERNIER MAIL que le candidat a envoyé à cette entreprise (c'est lui qu'on relance) :\n"
            f"<<<\n{precedent}\n>>>\n"
            "Avant d'écrire, observe ce mail : la formule d'appel utilisée (« Madame, Monsieur, », "
            "« Bonjour Monsieur X, », prénom…), le vouvoiement ou le tutoiement, le niveau de formalité, "
            "le poste visé et les arguments mis en avant.\n"
            "La relance doit garder EXACTEMENT le même ton et la même formule d'appel, rester cohérente avec "
            "ce mail (même poste, même interlocuteur), et y faire référence sans recopier ses paragraphes. "
            "Si ce mail était déjà une relance, ne répète pas les mêmes phrases.")
    else:
        consigne_ton = (f"Ton : {'formel, « Madame, Monsieur, »' if formel else 'vouvoiement mais plus direct, en nommant la personne'}.")
    try:
        corps = llm(
            f"{PROFIL}\n\n---\nÉcris un mail de RELANCE n°{nb} (court : 60 à 110 mots) pour la candidature "
            f"envoyée le {t_envoi:%d/%m/%Y} à « {ent} »"
            f"{' (contact : ' + contact + ')' if contact else ''}, restée sans réponse.\n"
            f"{consigne_ton}\n"
            "Rappelle brièvement la candidature, réaffirme l'intérêt, redis la disponibilité, "
            "propose un échange. "
            + ("Le mail précédent sera transféré en dessous. " if item is not None
               else "Le CV et le calendrier d'alternance sont joints à nouveau. ")
            + "Termine par « Cordialement, ». "
            "Pas de signature, pas d'objet : uniquement le corps du mail.")
    except Exception as e:
        say(f"   ⚠️ relance {ent} : échec de rédaction ({e})")
        return
    nom = (CFG.get("signature_formulaire") or {}).get("nom") or ""
    sujet = sujet or ("Candidature en alternance - " + nom).rstrip(" -")
    sujet_relance = "Relance : " + re.sub(r"^(TR|Fwd?|RE|Relance)\s*:\s*", "", sujet, flags=re.I)
    if item is None:
        say(f"   ℹ️ {ent} : mail d'origine introuvable dans Éléments envoyés, relance en nouveau mail")
    # Pas d'envoi différé posé par le script : il ne partirait que si l'Outlook classique est ouvert.
    # Tu planifies toi-même dans le nouvel Outlook (Envoyer -> Planifier l'envoi) : c'est le serveur qui envoie.
    ol.brouillon(mail, sujet_relance, texte_vers_html(corps), base=item,
                 pieces=CFG["pieces_jointes"] if item is None else ())
    suivi.set(row, "Statut", "Relance en brouillon")
    suivi.set(row, "Nb relances", nb)
    suivi.set(row, "Notes", f"Relance {nb} en brouillon, à planifier le {quand:%d/%m à %H:%M}. "
                            f"{suivi.get(row, 'Notes') or ''}".strip())
    ou = ("dans Gmail (flèche à côté d'Envoyer → Programmer l'envoi)" if type_messagerie() == "imap"
          else "dans le nouvel Outlook (Envoyer → Planifier l'envoi)")
    say(f"   📝 {ent} : relance {nb} en brouillon — à planifier {ou} pour le {quand:%a %d/%m à %H:%M}")
