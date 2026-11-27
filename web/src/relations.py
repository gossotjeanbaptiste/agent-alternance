"""Relations LinkedIn (export Connections.csv) qui travaillent dans une entreprise du tableau ; import de l'export
(Connections.csv ou l'archive .zip de LinkedIn) et ajout d'une relation à la main, fusionnés sans doublon."""
import csv
import io
import os
import zipfile
from datetime import date

import emplacements
from chemins import ROOT  # noqa: F401
from tableau import norm

FICHIER = emplacements.dossier("linkedin") / "Connections.csv"
COLONNES = ["First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On"]
TAILLE_MAX = 20 * 1024 * 1024      # export envoyé depuis la page (CSV, ou CSV dans l'archive) : 20 Mo au plus


def _lire_texte(texte):
    lignes = texte.splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.lstrip("﻿").startswith("First Name")), None)
    if debut is None:
        return None
    lignes[debut] = lignes[debut].lstrip("﻿")
    return list(csv.DictReader(lignes[debut:]))


def lire_relations():
    if not FICHIER.exists():
        return None
    return _lire_texte(FICHIER.read_text(encoding="utf-8", errors="replace")) or []


def correspondances(lignes_suivi, relations):
    """Pour chaque relation dont l'entreprise est dans le tableau (nom identique ou contenu dans l'autre)."""
    entreprises = {}
    for l in lignes_suivi:
        k = norm(l.get("Entreprise"))
        if len(k) >= 4:
            entreprises.setdefault(k, l)
    trouves = []
    for r in relations:
        k = norm(r.get("Company"))
        if len(k) < 4:
            continue
        l = entreprises.get(k) or next((v for e, v in entreprises.items() if e in k or k in e), None)
        if l:
            trouves.append({"entreprise": l.get("Entreprise"), "statut": l.get("Statut"),
                            "nom": f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip(),
                            "poste": r.get("Position"), "url": r.get("URL")})
    return sorted(trouves, key=lambda t: (str(t["entreprise"]).lower(), t["nom"]))


def _cle(r):
    """Une relation : son profil (URL) s'il est connu, sinon son nom et son entreprise."""
    url = str(r.get("URL") or "").strip().rstrip("/").lower()
    return url or (norm(f"{r.get('First Name', '')} {r.get('Last Name', '')}"), norm(r.get("Company")))


def _enregistrer(relations):
    """Écrit Connections.csv (format de LinkedIn), d'un seul coup ; l'ancien fichier est gardé en .bak."""
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    tampon = io.StringIO()
    tampon.write("Notes:\nRelations LinkedIn (export LinkedIn et ajouts depuis LMAgent)\n\n")
    w = csv.DictWriter(tampon, fieldnames=COLONNES, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(relations)
    tmp = FICHIER.with_name(FICHIER.name + ".tmp")
    tmp.write_text(tampon.getvalue(), encoding="utf-8")
    if FICHIER.exists():
        os.replace(FICHIER, FICHIER.with_name(FICHIER.name + ".bak"))
    os.replace(tmp, FICHIER)


def _fusionner(nouvelles):
    """Ajoute les relations absentes (même profil, ou même nom dans la même entreprise = déjà là). Renvoie le nombre ajouté."""
    actuelles = lire_relations() or []
    vues = {_cle(r) for r in actuelles}
    ajout = []
    for r in nouvelles:
        r = {c: str(r.get(c) or "").strip() for c in COLONNES}
        if (r["First Name"] or r["Last Name"]) and _cle(r) not in vues:
            vues.add(_cle(r))
            ajout.append(r)
    if ajout or not FICHIER.exists():
        _enregistrer(actuelles + ajout)
    return len(ajout)


def _contenu_csv(nom, donnees):
    """Texte de Connections.csv, envoyé tel quel ou dans l'archive .zip de l'export LinkedIn. ValueError sinon."""
    if nom.lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(io.BytesIO(donnees))
        except zipfile.BadZipFile:
            raise ValueError("archive .zip illisible")
        membre = next((m for m in z.infolist() if m.filename.lower().endswith("connections.csv")), None)
        if membre is None:
            raise ValueError("pas de Connections.csv dans l'archive : demande l'export des « Relations » à LinkedIn")
        if membre.file_size > TAILLE_MAX:
            raise ValueError("Connections.csv trop gros")
        donnees = z.read(membre)
    elif not nom.lower().endswith(".csv"):
        raise ValueError("envoie Connections.csv ou l'archive .zip de l'export LinkedIn")
    return donnees.decode("utf-8-sig", errors="replace")


def importer(fichier):
    """Export LinkedIn envoyé depuis la page (werkzeug FileStorage). Renvoie (ok, message)."""
    if fichier is None or not fichier.filename:
        return False, "Choisis le fichier de ton export LinkedIn."
    donnees = fichier.read(TAILLE_MAX + 1)
    if len(donnees) > TAILLE_MAX:
        return False, "Fichier trop gros (20 Mo maximum)."
    try:
        relations = _lire_texte(_contenu_csv(fichier.filename, donnees))
    except ValueError as e:
        return False, f"Import impossible : {e}."
    if relations is None or (relations and "Company" not in relations[0]):
        return False, "Ce fichier n'est pas un export des relations LinkedIn (colonnes « First Name », « Company »… absentes)."
    n = _fusionner(relations)
    return True, f"{len(relations)} relation(s) lue(s), {n} nouvelle(s) ajoutée(s) (les autres y étaient déjà)."


def ajouter(d):
    """Relation saisie dans la page : {prenom, nom, entreprise, poste, url}. Renvoie (ok, message)."""
    v = {k: str(d.get(k) or "").strip()[:200] for k in ("prenom", "nom", "entreprise", "poste", "url")}
    if not (v["prenom"] or v["nom"]) or not v["entreprise"]:
        return False, "Indique au moins le nom de la personne et son entreprise."
    if v["url"] and not v["url"].lower().startswith(("https://www.linkedin.com/", "https://linkedin.com/")):
        return False, "Le lien doit être celui de son profil LinkedIn (https://www.linkedin.com/in/…)."
    n = _fusionner([{"First Name": v["prenom"], "Last Name": v["nom"], "URL": v["url"], "Company": v["entreprise"],
                     "Position": v["poste"], "Connected On": f"{date.today():%d %b %Y}"}])
    nom = f"{v['prenom']} {v['nom']}".strip()
    return (True, f"{nom} ajouté(e) à tes relations.") if n else (False, f"{nom} est déjà dans tes relations.")
