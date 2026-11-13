"""Petits outils sur les adresses et le texte des mails."""
import re

import reglages

# modifiables dans la page Paramètres (section « Adresses mail »)
DOMAINES_PERSO = set(reglages.valeur("adresses.domaines_perso"))
GENERIQUES = tuple(reglages.valeur("adresses.prefixes_generiques"))

def texte_vers_html(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "".join(f"<p style='margin:0 0 10pt 0'>{p.replace(chr(10), '<br>')}</p>"
                   for p in re.split(r"\n\s*\n", t.strip()))


def est_adresse(mail):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", (mail or "").strip().lower()))


def domaine(mail):
    return mail.split("@")[-1].lower() if est_adresse(mail) else ""


def est_generique(mail):
    return (mail or "").split("@")[0].lower().split(".")[0] in GENERIQUES
