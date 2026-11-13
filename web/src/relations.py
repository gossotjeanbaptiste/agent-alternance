"""Relations LinkedIn (export Connections.csv) qui travaillent dans une entreprise du tableau."""
import csv

import emplacements
from chemins import ROOT  # noqa: F401
from tableau import norm

FICHIER = emplacements.dossier("linkedin") / "Connections.csv"


def lire_relations():
    if not FICHIER.exists():
        return None
    lignes = FICHIER.read_text(encoding="utf-8", errors="replace").splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.lstrip("﻿").startswith("First Name")), 0)
    return list(csv.DictReader(lignes[debut:]))


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
