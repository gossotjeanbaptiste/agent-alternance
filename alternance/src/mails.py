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


# --- brouillon sans adresse trouvée : le nom de l'entreprise dans le champ « À » --------------------------
# Domaine réservé « .invalid » (RFC 2606) : il ne reçoit jamais de mail, un envoi par oubli échoue aussitôt.
A_TROUVER = ".invalid"


def adresse_a_trouver(entreprise):
    """Adresse de remplacement propre à l'entreprise : « Xefi Lyon » -> a-trouver@xefi-lyon.invalid."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(entreprise or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50].strip("-")
    return f"a-trouver@{s or 'entreprise'}{A_TROUVER}"


def destinataire_a_trouver(entreprise):
    """Champ « À » d'un brouillon sans adresse : « Xefi (adresse à trouver) » <a-trouver@xefi.invalid>."""
    nom = re.sub(r'["<>\\]', "", str(entreprise or "")).strip() or "Entreprise"
    return f'"{nom} (adresse à trouver)" <{adresse_a_trouver(entreprise)}>'


def est_a_trouver(adresse):
    """Vrai pour une adresse de remplacement (brouillon dont l'adresse reste à trouver)."""
    return str(adresse or "").strip().lower().endswith(A_TROUVER)
