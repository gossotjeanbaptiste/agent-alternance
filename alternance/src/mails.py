"""Petits outils sur les adresses et le texte des mails."""
import re

DOMAINES_PERSO = {"gmail.com", "outlook.fr", "outlook.com", "hotmail.fr", "hotmail.com", "yahoo.fr",
                  "yahoo.com", "orange.fr", "free.fr", "laposte.net", "wanadoo.fr", "icloud.com",
                  "live.fr", "sfr.fr"}
GENERIQUES = ("contact", "rh", "recrutement", "recrutements", "jobs", "job", "carriere", "carrieres",
              "emploi", "info", "infos", "hello", "bonjour", "accueil", "secretariat", "candidature",
              "candidatures", "drh", "admin", "direction", "talent", "talents")


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
