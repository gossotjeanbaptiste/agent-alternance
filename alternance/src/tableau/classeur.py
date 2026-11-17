"""Le fichier Excel du suivi : création, lignes, lecture / écriture d'une case, enregistrement sans risque."""
import os
import re
from datetime import datetime
from pathlib import Path

import commun
from commun import say
from mails import DOMAINES_PERSO, domaine
from .mise_en_forme import mettre_en_forme
from .statuts import COLS, COLS_A_CONTACTER, ancien_statut
from .texte import cle_lieu, norm


class Suivi:
    def __init__(self, path):
        import openpyxl
        self.path = path
        self.wb = openpyxl.load_workbook(path) if path.exists() else self._nouveau()
        self.ws = self.wb["Suivi"]
        self.ac = self.wb["À contacter"] if "À contacter" in self.wb.sheetnames else None
        self.h = {c.value: i for i, c in enumerate(self.ws[1]) if c.value}
        for col in COLS:  # ajoute les colonnes manquantes si le fichier vient d'ailleurs
            if col not in self.h:
                self.ws.cell(1, len(self.h) + 1, col)
                self.h[col] = len(self.h)
        for r in self.rows():  # anciens noms de statut (enregistrés au prochain « save »)
            st = self.get(r, "Statut")
            nouveau = ancien_statut(st, self.get(r, "Notes"), self.get(r, "Source"))
            if nouveau != st:
                self.set(r, "Statut", nouveau)

    @staticmethod
    def _nouveau():
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suivi"
        ws.append(COLS)
        ac = wb.create_sheet("À contacter")
        ac.append(COLS_A_CONTACTER)
        for s in (ws, ac):
            for c in s[1]:
                c.font = openpyxl.styles.Font(bold=True)
            s.freeze_panes = "A2"
        return wb

    def rows(self):
        for r in self.ws.iter_rows(min_row=2):
            if any(c.value for c in r):
                yield r

    def get(self, row, col):
        return row[self.h[col]].value if self.h[col] < len(row) else None

    def set(self, row, col, val):
        # (ws.cell(ligne, col, None) ne vide pas la case : openpyxl ignore la valeur None)
        self.ws.cell(row[0].row, self.h[col] + 1).value = val

    def add(self, **vals):
        self.ws.append([vals.get(c, "") for c in sorted(self.h, key=self.h.get)])

    def deja_vus(self):
        """Tout ce qui identifie une entreprise déjà présente : {nom: villes}, domaines mail, SIRET.
        La ville permet d'avoir plusieurs établissements du même nom (adresses différentes)."""
        noms, domaines, sirets = {}, set(), set()
        for r in self.rows():
            n = norm(self.get(r, "Entreprise"))
            if n:
                noms.setdefault(n, set()).add(cle_lieu(self.get(r, "Lieu")))
            d = domaine(str(self.get(r, "Email") or "").strip())
            if d and d not in DOMAINES_PERSO:
                domaines.add(d)
            sirets |= set(re.findall(r"\b\d{14}\b", f"{self.get(r, 'Notes')} {self.get(r, 'Lien')}"))
        return noms, domaines, sirets

    def mise_en_forme(self):
        mettre_en_forme(self)

    def enregistrer_sur(self, chemin=None):
        """Enregistre sans risque d'abîmer le fichier : écrit à côté puis remplace l'ancien d'un seul coup
        (une routine annulée ou une coupure en plein enregistrement laisse l'ancien tableau intact).
        Lève PermissionError si le tableau est ouvert dans Excel."""
        chemin = Path(chemin or self.path)
        provisoire = chemin.with_name(chemin.stem + ".enregistrement.xlsx")
        self.wb.save(provisoire)
        try:
            os.replace(provisoire, chemin)
        except PermissionError:
            provisoire.unlink(missing_ok=True)
            raise

    def save(self):
        if commun.ESSAI:
            return
        self.mise_en_forme()
        try:
            self.enregistrer_sur()
        except PermissionError:
            alt = self.path.with_name(f"{self.path.stem}_{datetime.now():%Y%m%d_%H%M}.xlsx")
            self.wb.save(alt)
            say(f"⚠️ Tableau ouvert ailleurs : sauvegardé dans {alt.name} (à fusionner)")
