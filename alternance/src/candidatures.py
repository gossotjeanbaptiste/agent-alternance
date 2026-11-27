"""Choix des nouvelles entreprises et rédaction des candidatures en brouillon."""
from datetime import date

import commun
import reponses
from commun import CFG, PROFIL, interdits, say
from mails import destinataire_a_trouver, domaine, est_generique, texte_vers_html
from modele import llm_json
from sites import explorer_site, trouver_site
from sources import depuis_a_contacter, depuis_lba, depuis_linkedin
from tableau import FORMULAIRE, LBA, deja_contactee, norm, retenir

def rediger_candidature(o):
    mail = o.get("email") or ""
    formel = est_generique(mail) or not o.get("contact")
    r = llm_json(
        f"{PROFIL}\n\n---\nÉcris un mail de candidature pour cette entreprise :\n"
        f"- Entreprise : {o['entreprise']}\n- Poste / offre : {o.get('poste') or 'candidature spontanée'}\n"
        f"- Lieu : {o.get('lieu') or '?'}\n- Contact : {o.get('contact') or 'inconnu'}\n"
        f"- Ce qu'on sait de l'entreprise / de l'offre : {o.get('infos') or 'rien de plus'}\n"
        f"Ton : {'formel, « Madame, Monsieur, »' if formel else 'vouvoiement, plus direct, « Bonjour Madame/Monsieur Nom, »'}.\n"
        f"{reponses.NE_PAS_INVENTER}{interdits()}"
        '{"objet": "objet du mail", "corps": "corps du mail, paragraphes séparés par une ligne vide"}')
    return r["objet"], r["corps"]


def nouvelles_candidatures(suivi, ol):
    n = CFG["mails_par_jour"]
    say(f"🔎 Recherche de {n} nouvelles entreprises...")
    commun.etape("Recherche de nouvelles entreprises", "liste perso, alertes LinkedIn, La Bonne Alternance")
    noms, domaines, sirets = suivi.deja_vus()
    choix, sans_mail = [], []
    recherches, maxi = 0, CFG["la_bonne_alternance"].get("recherches_site_max", 30)
    # Entreprises distinctes écartées car déjà connues : les recherches La Bonne Alternance gare par gare
    # se chevauchent (rayon), la même entreprise revient des dizaines de fois ; on ne la compte qu'une fois.
    ignorees = set()
    # 1) ta liste perso d'abord, 2) alertes LinkedIn, 3) La Bonne Alternance (gare par gare).
    # Comptent comme candidatures valables : adresse mail réelle, ta liste perso,
    # ou candidature spontanée possible sur La Bonne Alternance. Le reste sert de réserve.
    for source in (lambda: depuis_a_contacter(suivi), lambda: depuis_linkedin(ol), depuis_lba):
        if len(choix) >= n:
            break
        for o in source():
            if deja_contactee(o, noms, domaines, sirets):
                ignorees.add(norm(o["entreprise"]))
                continue
            if not o.get("email") and recherches < maxi:
                # pas d'adresse : on cherche le site de l'entreprise (s'il n'est pas connu),
                # puis une adresse ou un formulaire de contact sur ce site
                recherches += 1
                commun.etape("Recherche des sites et adresses", f"{o['entreprise']} — {len(choix)}/{n} retenue(s)",
                             ligne=f"   ⏳ Recherche du site et de l'adresse de {o['entreprise']}…")
                if not o.get("site"):
                    o["site"] = trouver_site(o["entreprise"], o.get("lieu"))
                if o.get("site"):
                    trouve = explorer_site(o["site"], lieu=o.get("lieu") or "")
                    o["site"], o["email"], o["formulaire"] = trouve["site"], trouve["email"], trouve["formulaire"]
                    if trouve.get("ecarte"):   # site d'une entreprise hors de France : rien n'en est gardé
                        say(f"   🌍 {o['entreprise']} : site écarté ({trouve['ecarte']})")
                if o["email"] and deja_contactee(o, noms, domaines, sirets):  # même domaine déjà contacté
                    ignorees.add(norm(o["entreprise"]))
                    continue
            # on retient l'entreprise pour ne pas la reprendre deux fois aujourd'hui
            retenir(noms, o)
            if o.get("siret"):
                sirets.add(o["siret"])
            if o.get("email"):
                domaines.add(domaine(o["email"]))
            valable = (o.get("email") or o.get("formulaire") or o["source"] == "Liste perso"
                       or o.get("lba_postulable"))
            (choix if valable else sans_mail).append(o)
            if len(choix) >= n:
                break
    choix += sans_mail[: max(0, n - len(choix))]
    if ignorees:
        say(f"   {len(ignorees)} entreprise(s) ignorée(s) car déjà présentes dans le tableau "
            "ou déjà retenues aujourd'hui")
    if not choix:
        say("   Aucune nouvelle entreprise trouvée (remplis la feuille « À contacter » ou ajoute un jeton La Bonne Alternance).")
        return
    for k, o in enumerate(choix, 1):
        commun.etape("Rédaction des candidatures", o["entreprise"], k, len(choix),
                     ligne=f"   ⏳ Rédaction pour {o['entreprise']} ({k}/{len(choix)})…")
        try:
            objet, corps = rediger_candidature(o)
        except Exception as e:
            say(f"   ⚠️ {o['entreprise']} : rédaction impossible ({e})")
            continue
        lba = bool(o.get("lba_postulable"))  # formulaire « Postuler » disponible sur La Bonne Alternance
        notes = [f"SIRET {o['siret']}"] if o.get("siret") else []
        if o.get("activite"):   # activité officielle (code NAF) : redonnée au modèle s'il réécrit depuis le tableau
            notes.append(f"Activité : {o['activite']}")
        if o.get("site"):
            notes.append(f"Site : {o['site']}")
        if o.get("formulaire"):
            notes.append(f"Formulaire : {o['formulaire']}")
        if o.get("email"):
            statut = "Brouillon"
        elif lba:
            # pas d'adresse, mais candidature spontanée possible via le formulaire La Bonne Alternance :
            # le brouillon sert de lettre à copier-coller dans ce formulaire
            statut = LBA
            objet = f"[À postuler sur La Bonne Alternance] {objet}"
            corps = f"Lien pour postuler : {o['lien']}\n\n{corps}"
        elif o.get("formulaire"):
            # pas d'adresse, mais un formulaire de contact sur le site de l'entreprise
            statut = FORMULAIRE
            if o.get("lien"):
                quoi = "Fiche La Bonne Alternance (pas de bouton Postuler)" if "labonnealternance" in o["lien"] else "Offre"
                notes.append(f"{quoi} : {o['lien']}")
            o["lien"] = o["formulaire"]
            objet = f"[À postuler via le formulaire du site] {objet}"
            corps = f"Lien pour postuler : {o['lien']}\n\n{corps}"
        else:
            statut = "Brouillon (adresse à trouver)"
        if statut in (LBA, FORMULAIRE):
            # candidature par formulaire : pas de brouillon dans la messagerie, la lettre est gardée
            # à part et affichée sur la page « À postuler » (et dans postuler.py)
            reponses.enregistrer_lettre(o["lien"], corps.split("\n\n", 1)[1])
        else:
            # pas d'adresse trouvée : le nom de l'entreprise dans le champ « À » (adresse de remplacement en .invalid,
            # à remplacer par la vraie avant d'envoyer) pour savoir à qui le brouillon est destiné
            a = o.get("email") or destinataire_a_trouver(o["entreprise"])
            ol.brouillon(a, objet, texte_vers_html(corps), pieces=commun.pieces_jointes())
        # le formulaire La Bonne Alternance (offre ou candidature spontanée) pose aussi trois questions : réponses prêtes
        if reponses.questions_attendues(statut, o.get("poste")):
            try:
                reponses.enregistrer(o["lien"], reponses.rediger_reponses(o))
            except Exception as e:
                say(f"   ⚠️ {o['entreprise']} : réponses du formulaire non écrites ({e})")
        suivi.add(**{"Date ajout": date.today(), "Entreprise": o["entreprise"], "Poste": o.get("poste"),
                     "Lieu": o.get("lieu"), "Source": o.get("source"), "Lien": o.get("lien"),
                     "Contact": o.get("contact"), "Email": o.get("email"),
                     "Téléphone": o.get("telephone", ""), "Statut": statut,
                     "Nb relances": 0, "Notes": " | ".join(notes)})
        if "_ligne" in o and o["_ligne"][2] is not None and not commun.ESSAI:
            ws, ligne, col = o["_ligne"]
            ws.cell(ligne, col + 1, f"oui ({date.today():%d/%m})")
        quoi = "lettre prête, à postuler sur la page « À postuler »" if statut in (LBA, FORMULAIRE) else "candidature en brouillon"
        say(f"   📝 {o['entreprise']} : {quoi} ({statut})")
