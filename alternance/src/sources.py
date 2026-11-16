"""Où trouver de nouvelles entreprises : feuille « À contacter », alertes LinkedIn, La Bonne Alternance."""
import json
import math
import random
import re
import unicodedata
import urllib.parse
import urllib.request

import refus
import reglages
from commun import CFG, say
from modele import llm_json

def depuis_a_contacter(suivi):
    """Feuille « À contacter » : ce que tu y colles est prioritaire."""
    if not suivi.ac:
        return []
    h = {c.value: i for i, c in enumerate(suivi.ac[1]) if c.value}
    out = []
    for r in suivi.ac.iter_rows(min_row=2):
        v = lambda k: r[h[k]].value if k in h and h[k] < len(r) else None  # noqa: E731
        if v("Entreprise") and not v("Traité"):
            out.append({"entreprise": v("Entreprise"), "poste": v("Poste") or "", "lieu": v("Lieu") or "",
                        "contact": v("Contact") or "", "email": (v("Email") or "").strip(),
                        "site": (v("Site") or "").strip(),
                        # SIRET noté dans les infos (ajout depuis la page « Écartées ») : distingue les établissements
                        "siret": next(iter(re.findall(r"SIRET (\d{14})", str(v("Infos") or ""))), ""),
                        "lien": v("Lien") or "", "infos": v("Infos") or "", "source": "Liste perso",
                        "_ligne": (suivi.ac, r[0].row, h.get("Traité"))})
    return out


def depuis_linkedin(ol):
    c = CFG["alertes_linkedin"]
    if not c["actif"]:
        return []
    out = []
    for m in ol.recus(jours=c["jours"]):
        if not any(e in m["de"] for e in c["expediteurs"]):
            continue
        try:
            offres = llm_json(
                "Voici un mail d'alerte emploi LinkedIn. Extrais les offres :\n"
                '[{"entreprise": "", "poste": "", "lieu": ""}]\n---\n' + m["corps"][:4000])
            for o in offres:
                if o.get("entreprise"):
                    out.append({**o, "contact": "", "email": "", "infos": "",
                                "lien": f"Alerte LinkedIn du {m['date']:%d/%m}", "source": "LinkedIn"})
        except Exception as e:
            say(f"   ⚠️ alerte LinkedIn illisible ({e})")
    return out


def _sans_accents(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def _distance_km(a, b):
    """Distance à vol d'oiseau entre deux points {lat, lon}."""
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def poids_villes(c):
    """Poids de chaque ville (entre poids_min et 1) :
    - 1 pour le centre et les villes prioritaires (même poids que le centre) ;
    - sinon il baisse avec la distance au centre : divisé par 2 tous les « demi_distance_km » ;
    - un "poids" écrit à la main sur une ville dans la config passe avant tout."""
    centre = c.get("centre")
    prio = {_sans_accents(n) for n in c.get("villes_prioritaires", [])}
    demi = float(c.get("demi_distance_km", 30))
    mini = float(c.get("poids_min", 0.05))
    res = {}
    for v in c["villes"]:
        if "poids" in v:
            p = float(v["poids"])
        elif not centre or _sans_accents(v["nom"]) in prio or _sans_accents(v["nom"]) == _sans_accents(centre["nom"]):
            p = 1.0
        else:
            p = max(mini, 0.5 ** (_distance_km(v, centre) / demi))
        res[v["nom"]] = round(p, 3)
    return res


def ordre_pondere(c):
    """Ordre de passage des villes : tirage au hasard pondéré (une ville de poids 1 passe
    en général avant une ville de poids 0,2, mais l'ordre varie d'un jour à l'autre)."""
    poids = poids_villes(c)
    return sorted(c["villes"], key=lambda v: random.random() ** (1 / max(poids[v["nom"]], 1e-6)), reverse=True)


# Activités (codes NAF) acceptées pour les candidatures spontanées : logiciel ou matériel informatique.
# Un préfixe suffit : "62" couvre 62.01Z, 62.02A… Modifiable dans config_alternance.json (« naf_acceptes »).
NAF_ACCEPTES = reglages.NAF_ACCEPTES   # modifiable dans la page Paramètres (section « La Bonne Alternance »)


def activite_acceptee(code, c):
    """Vrai si le code NAF est dans les activités informatiques acceptées (ou inconnu : on garde)."""
    if not code:
        return True
    return any(str(code).startswith(p) for p in c.get("naf_acceptes", NAF_ACCEPTES))


def depuis_lba():
    c = CFG["la_bonne_alternance"]
    if not c["actif"]:
        return []
    if not c["jeton_api"]:
        say("   ℹ️ La Bonne Alternance : pas de jeton API dans config_alternance.json, source ignorée")
        return
    villes = ordre_pondere(c)  # les villes au poids fort passent en premier (plus souvent)
    for v in villes:
        out, ecartees, a_noter = [], [], []
        q = urllib.parse.urlencode({"romes": ",".join(c["codes_rome"]), "latitude": v["lat"],
                                    "longitude": v["lon"], "radius": c["rayon_km"]})
        req = urllib.request.Request(f"https://api.apprentissage.beta.gouv.fr/api/job/v1/search?{q}",
                                     headers={"Authorization": f"Bearer {c['jeton_api']}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
        except Exception as e:
            say(f"   ⚠️ La Bonne Alternance ({v['nom']}) : {e}")
            continue
        # les vraies offres d'abord, puis les entreprises susceptibles de recruter
        for item in (data.get("jobs") or []) + (data.get("recruiters") or []):
            wp = item.get("workplace") or {}
            offer = item.get("offer") or {}
            apply = item.get("apply") or {}
            loc = wp.get("location") or {}
            nom = wp.get("brand") or wp.get("name") or wp.get("legal_name")
            if not nom:
                continue
            naf_info = (wp.get("domain") or {}).get("naf") or {}
            naf = naf_info.get("label") or ""
            # candidature spontanée : seulement les entreprises dont l'activité est l'informatique
            # (logiciel ou matériel). Les vraies offres d'emploi passent toujours (poste déjà ciblé).
            if not offer and not activite_acceptee(naf_info.get("code"), c):
                ecartees.append(f"{nom} ({naf or 'activité inconnue'})")
                code = f" ({naf_info['code']})" if naf_info.get("code") else ""
                a_noter.append({"Entreprise": nom.title() if nom.isupper() else nom, "SIRET": str(wp.get("siret") or ""),
                                "Code NAF": naf_info.get("code") or "", "Activité": naf or "inconnue",
                                "Adresse": loc.get("address") or "", "Site": wp.get("website") or "",
                                "Recherche": v["nom"],
                                "Raison": f"Activité hors informatique : {naf or 'inconnue'}{code}"})
                continue
            infos = [str(offer.get("description") or wp.get("description") or "")[:1200]]
            if naf:
                infos.append(f"Activité : {naf}")
            # (taille de l'entreprise volontairement absente : le modèle la recopiait dans les mails)
            if wp.get("website"):
                infos.append(f"Site : {wp['website']}")
            # Candidature possible sur le site de La Bonne Alternance (bouton « Postuler ») seulement
            # si elle a un destinataire pour l'entreprise (recipient_id) ; sinon la page n'est qu'une fiche.
            postulable = bool(apply.get("recipient_id")) or bool(offer and apply.get("url"))
            out.append({
                "entreprise": nom.title() if nom.isupper() else nom,
                "poste": offer.get("title") or "Candidature spontanée",
                "lieu": loc.get("address") or v["nom"], "contact": "", "email": "",
                "site": wp.get("website") or "", "telephone": apply.get("phone") or "",
                "siret": str(wp.get("siret") or ""),
                "lien": apply.get("url") or "", "lba_postulable": postulable,
                "infos": " | ".join(i for i in infos if i),
                "source": f"La Bonne Alternance ({v['nom']})"})
        if ecartees:
            say(f"   🚫 {v['nom']} : {len(ecartees)} entreprise(s) hors informatique écartée(s) "
                f"({', '.join(ecartees[:3])}{'…' if len(ecartees) > 3 else ''})")
            refus.noter(a_noter)  # liste complète : alternance/donnees/entreprises_refusees.csv
        yield from out
