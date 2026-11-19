"""Formulaire « Candidature simplifiée » de La Bonne Alternance prérempli dans Chrome (bouton « Ouvrir le formulaire
prérempli » de la page À postuler). Nom, prénom, mail, téléphone, situation, message (la lettre), CV et réponses aux
questions sont remplis ; la fenêtre reste ouverte : c'est l'utilisateur qui relit et clique « J'envoie ma candidature
spontanée ». Le script ne clique JAMAIS sur l'envoi."""
import json
import re
from pathlib import Path

import commun
import reglages

TAILLE_CV_MAX = 3 * 1024 * 1024        # limite du site
FORMATS_CV = (".pdf", ".docx", ".doc")
# question du site -> clé des réponses de LMAgent (reglages.QUESTIONS), reconnue à des mots de son intitulé
MOTS_QUESTIONS = {"motivations": ("pourquoi", "rejoindre", "motivation"), "missions": ("mission",),
                  "experiences": ("expérience", "experience", "stage")}
SITUATIONS = {"déjà inscrit(e) en formation": 0, "pas encore inscrit(e) en formation": 1}


def nom_et_prenom(complet):
    """(nom, prénom) depuis « Prénom NOM » : les mots en majuscules forment le nom, sinon le dernier mot."""
    mots = str(complet or "").split()
    nom = [m for m in mots if m.isupper() and len(m) > 1]
    if not nom and mots:
        nom = mots[-1:]
    prenom = [m for m in mots if m not in nom]
    return " ".join(nom), " ".join(prenom)


def choisir_cv(chemins):
    """Le CV parmi les pièces jointes : PDF ou Word de moins de 3 Mo, celui dont le nom contient « cv » d'abord."""
    ok = [Path(c) for c in chemins if Path(c).suffix.lower() in FORMATS_CV and Path(c).exists()
          and Path(c).stat().st_size <= TAILLE_CV_MAX]
    ok.sort(key=lambda p: (not re.search(r"(^|[^a-z])cv([^a-z]|$)", p.stem.lower()), p.suffix.lower() != ".pdf"))
    return ok[0] if ok else None


def cle_question(intitule):
    """Clé de la réponse LMAgent qui correspond à une question du site (None si aucune)."""
    t = str(intitule or "").lower()
    return next((cle for cle, mots in MOTS_QUESTIONS.items() if any(m in t for m in mots)), None)


def champs(lettre, reponses):
    """Ce que le formulaire recevra : identité (signature des formulaires), situation, message et réponses."""
    s = commun.CFG.get("signature_formulaire") or {}
    nom, prenom = nom_et_prenom(s.get("nom"))
    return {"applicant_last_name": nom, "applicant_first_name": prenom,
            "applicant_email": str(s.get("email") or "").strip(),
            "applicant_phone": re.sub(r"[^\d+]", "", str(s.get("telephone") or "")),
            "applicant_message": str(lettre or "").strip(),
            "situation": SITUATIONS.get(reglages.valeur("la_bonne_alternance.situation")),
            "reponses": {cle: str(texte or "").strip() for cle, texte in (reponses or {}).items() if cle != "lettre"}}


# Remplit les champs comme une saisie au clavier (le site est en React : changer .value ne suffit pas).
REMPLIR = """((d, mots) => {
  const saisir = (el, v) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    ['input', 'change', 'blur'].forEach(t => el.dispatchEvent(new Event(t, {bubbles: true})));
  };
  const faits = [];
  for (const nom of ['applicant_last_name', 'applicant_first_name', 'applicant_email', 'applicant_phone', 'applicant_message']) {
    const el = document.getElementById(nom);
    if (el && d[nom]) { saisir(el, d[nom]); faits.push(nom); }
  }
  const radios = document.querySelectorAll('input[name=applicant_inscription_formation]');
  if (d.situation !== null && d.situation !== undefined && radios[d.situation]) { radios[d.situation].click(); faits.push('situation'); }
  document.querySelectorAll('textarea[id^=custom_question_]').forEach(el => {
    const t = ((el.labels && el.labels[0]) ? el.labels[0].innerText : '').toLowerCase();
    const cle = Object.keys(mots).find(k => mots[k].some(m => t.includes(m)));
    if (cle && d.reponses[cle]) { saisir(el, d.reponses[cle].slice(0, 2000)); faits.push(cle); }
  });
  return faits;
})"""
BOUTON = "[...document.querySelectorAll('button')].find(b => /candidature simplifi/i.test(b.innerText))"


def ouvrir_et_remplir(lien, donnees, cv=None):
    """Ouvre la fiche dans Chrome, ouvre « Candidature simplifiée » et remplit tout. Renvoie (ok, message)."""
    import chrome
    onglet = chrome.ouvrir(lien)
    try:
        onglet.montrer()
        if not onglet.attendre(f"document.readyState === 'complete' && !!{BOUTON}", delai=25):
            sans = onglet.evaluer("/pas d.(e-?mail|contact) pour cette entreprise/i.test(document.body.innerText)")
            return False, ("La Bonne Alternance n'a plus de contact pour cette entreprise : pas de formulaire. "
                           "La page est ouverte dans Chrome (téléphone ou site éventuels)." if sans else
                           "Bouton « Candidature simplifiée » introuvable : la page est ouverte dans Chrome, "
                           "remplis-la à la main.")
        onglet.evaluer(f"{BOUTON}.click()")
        if not onglet.attendre("!!document.getElementById('applicant_last_name')", delai=15):
            return False, "Le formulaire ne s'est pas ouvert : la page est dans Chrome, remplis-la à la main."
        faits = onglet.evaluer(f"{REMPLIR}({json.dumps(donnees)}, {json.dumps(MOTS_QUESTIONS)})") or []
        message = f"Formulaire prérempli dans Chrome ({len(faits)} champs)"
        if cv:
            try:
                onglet.joindre("#applicant_attachment_name", cv)
                message += f", CV joint ({Path(cv).name})"
            except RuntimeError as e:
                message += f" ; CV à joindre à la main ({e})"
        else:
            message += " ; aucun CV (PDF ou Word de moins de 3 Mo) dans les pièces jointes : joins-le à la main"
        return True, message + ". Relis puis clique « J'envoie ma candidature spontanée », et enfin « ✅ Envoyée » ici."
    finally:
        onglet.fermer()
