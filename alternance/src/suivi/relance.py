"""Brouillon de relance écrit par le modèle, dans le ton du dernier mail envoyé (jamais envoyé par le script :
tu le planifies toi-même dans ta messagerie)."""
import re
from datetime import date

import commun
import reglages
from commun import CFG, PROFIL, interdits, say
from jours import heure_aleatoire, prochain_ouvrable
from mails import est_generique, texte_vers_html
from messagerie import texte_mail, type_messagerie
from modele import llm
from tableau import as_date


def _consigne_ton(precedent, formel):
    if not precedent:
        return f"Ton : {'formel, « Madame, Monsieur, »' if formel else 'vouvoiement mais plus direct, en nommant la personne'}."
    return ("Voici le DERNIER MAIL que le candidat a envoyé à cette entreprise (c'est lui qu'on relance) :\n"
            f"<<<\n{precedent}\n>>>\n"
            "Avant d'écrire, observe ce mail : la formule d'appel utilisée (« Madame, Monsieur, », "
            "« Bonjour Monsieur X, », prénom…), le vouvoiement ou le tutoiement, le niveau de formalité, "
            "le poste visé et les arguments mis en avant.\n"
            "La relance doit garder EXACTEMENT le même ton et la même formule d'appel, rester cohérente avec "
            "ce mail (même poste, même interlocuteur), et y faire référence sans recopier ses paragraphes. "
            "Si ce mail était déjà une relance, ne répète pas les mêmes phrases.")


def _rediger(ent, contact, nb, t_envoi, consigne_ton, transfert):
    return llm(
        f"{PROFIL}\n\n---\nÉcris un mail de RELANCE n°{nb} (court : {reglages.valeur('redaction.longueur_relance')}) pour la candidature "
        f"envoyée le {t_envoi:%d/%m/%Y} à « {ent} »"
        f"{' (contact : ' + contact + ')' if contact else ''}, restée sans réponse.\n"
        f"{consigne_ton}\n"
        "Rappelle brièvement la candidature, réaffirme l'intérêt, redis la disponibilité, "
        "propose un échange. "
        + ("Le mail précédent sera transféré en dessous. " if transfert
           else "Le CV et le calendrier d'alternance sont joints à nouveau. ")
        + "Termine par « Cordialement, ». "
        "Pas de signature, pas d'objet : uniquement le corps du mail." + interdits())


def preparer_relance(suivi, ol, row, t_envoi, sujet, item):
    ent, mail = suivi.get(row, "Entreprise"), suivi.get(row, "Email")
    contact = suivi.get(row, "Contact") or ""
    nb = int(suivi.get(row, "Nb relances") or 0) + 1
    prevue = as_date(suivi.get(row, "Relance prévue")) or date.today()
    jour = prevue if prevue > date.today() else prochain_ouvrable(date.today(), inclus=False)
    quand = heure_aleatoire(jour)
    formel = est_generique(mail) or not contact
    try:
        corps = _rediger(ent, contact, nb, t_envoi, _consigne_ton(texte_mail(item), formel), item is not None)
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
                 pieces=commun.pieces_jointes() if item is None else ())
    suivi.set(row, "Statut", "Relance en brouillon")
    suivi.set(row, "Nb relances", nb)
    suivi.set(row, "Notes", f"Relance {nb} en brouillon, à planifier le {quand:%d/%m à %H:%M}. "
                            f"{suivi.get(row, 'Notes') or ''}".strip())
    ou = ("dans Gmail (flèche à côté d'Envoyer → Programmer l'envoi)" if type_messagerie() == "imap"
          else "dans le nouvel Outlook (Envoyer → Planifier l'envoi)")
    say(f"   📝 {ent} : relance {nb} en brouillon — à planifier {ou} pour le {quand:%a %d/%m à %H:%M}")
