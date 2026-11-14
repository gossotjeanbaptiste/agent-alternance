"""Le tableau de suivi Excel : colonnes, statuts, lecture / écriture, détection des doublons."""
import re
import unicodedata
from datetime import date, datetime

import commun
from commun import say
from mails import DOMAINES_PERSO, domaine

COLS = ["Date ajout", "Entreprise", "Poste", "Lieu", "Source", "Lien", "Contact", "Email", "Téléphone",
        "Statut", "Date envoi", "Dernière action", "Relance prévue", "Nb relances",
        "Dernière réponse", "Notes"]
STATUTS = {  # statut -> couleur de fond
    "Brouillon": "FFF2CC", "Brouillon (adresse à trouver)": "FCE4D6",
    "À postuler (La Bonne Alternance)": "E2EFDA", "À postuler (formulaire du site)": "E2EFDA",
    "Candidaté (mail)": "DDEBF7", "Relance en brouillon": "FFF2CC", "Relance programmée": "DDEBF7", "Relancé": "BDD7EE",
    "Candidaté (La Bonne Alternance)": "DDEBF7", "Candidaté (formulaire du site)": "DDEBF7",
    "Candidaté (LinkedIn)": "DDEBF7", "Candidaté (autre canal)": "EDEDED",
    "Réponse à lire": "FFE699", "Réponse positive": "C6EFCE", "Entretien": "A9D08E",
    "Accepté": "70AD47", "Refus": "F4B6B6", "Adresse invalide": "FF9999", "Sans réponse": "D9D9D9",
    "Abandonné": "BFBFBF",
}
LBA = "À postuler (La Bonne Alternance)"
FORMULAIRE = "À postuler (formulaire du site)"
A_POSTULER = (LBA, FORMULAIRE)
# candidature envoyée : par mail (suivie et relancée automatiquement) ou par un autre canal
MAIL = "Candidaté (mail)"
C_LBA = "Candidaté (La Bonne Alternance)"
C_FORMULAIRE = "Candidaté (formulaire du site)"
C_LINKEDIN = "Candidaté (LinkedIn)"
C_AUTRE = "Candidaté (autre canal)"
HORS_MAIL = (C_LBA, C_FORMULAIRE, C_LINKEDIN, C_AUTRE)


def ancien_statut(statut, notes, source=""):
    """Anciens noms de statut -> nouveaux (« Envoyé », « Candidaté (hors mail) »)."""
    if statut == "Envoyé":
        return MAIL
    if statut == "Candidaté (hors mail)":
        n = (notes or "").lower()
        via = n.split("candidature via", 1)[1] if "candidature via" in n else ""
        if via:
            return statut_par_canal(via)
        if "bonne alternance" in (source or "").lower():  # envoyée depuis la page « À postuler »
            return C_LBA
        return C_AUTRE
    return statut


def statut_par_canal(canal):
    """Statut « Candidaté (…) » d'après le canal saisi (« La Bonne Alternance », « site », « LinkedIn »…)."""
    c = (canal or "").lower()
    if "bonne" in c or "labonnealternance" in c or "lba" in c:
        return C_LBA
    if "linkedin" in c:
        return C_LINKEDIN
    if any(m in c for m in ("formulaire", "form ", "form contact", "site", "contact", "http")):
        return C_FORMULAIRE
    return C_AUTRE
COLS_A_CONTACTER = ["Entreprise", "Poste", "Lieu", "Contact", "Email", "Lien", "Infos", "Traité", "Site"]


class Suivi:
    def __init__(self, path):
        import openpyxl
        self.path = path
        if path.exists():
            self.wb = openpyxl.load_workbook(path)
        else:
            self.wb = openpyxl.Workbook()
            ws = self.wb.active
            ws.title = "Suivi"
            ws.append(COLS)
            ac = self.wb.create_sheet("À contacter")
            ac.append(COLS_A_CONTACTER)
            for s in (ws, ac):
                for c in s[1]:
                    c.font = openpyxl.styles.Font(bold=True)
                s.freeze_panes = "A2"
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
        """Tout ce qui identifie une entreprise déjà présente : nom, domaine mail, SIRET."""
        noms, domaines, sirets = set(), set(), set()
        for r in self.rows():
            n = norm(self.get(r, "Entreprise"))
            if n:
                noms.add(n)
            d = domaine(str(self.get(r, "Email") or "").strip())
            if d and d not in DOMAINES_PERSO:
                domaines.add(d)
            sirets |= set(re.findall(r"\b\d{14}\b", f"{self.get(r, 'Notes')} {self.get(r, 'Lien')}"))
        return noms, domaines, sirets

    def mise_en_forme(self):
        from openpyxl.styles import Font, PatternFill
        from openpyxl.worksheet.datavalidation import DataValidation
        ws = self.ws
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F4E78")
        larg = {"Entreprise": 28, "Poste": 30, "Lieu": 18, "Lien": 30, "Contact": 22, "Email": 34,
                "Statut": 26, "Dernière réponse": 50, "Notes": 50}
        from openpyxl.utils import get_column_letter
        for col, i in self.h.items():
            L = get_column_letter(i + 1)
            ws.column_dimensions[L].width = larg.get(col, 14)
            if col.startswith("Date") or col in ("Dernière action", "Relance prévue"):
                for r in range(2, ws.max_row + 1):
                    ws[f"{L}{r}"].number_format = "DD/MM/YYYY"
        for row in self.rows():
            st = self.get(row, "Statut")
            if st in STATUTS:
                row[self.h["Statut"]].fill = PatternFill("solid", fgColor=STATUTS[st])
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        # Liste déroulante des statuts : lue dans une feuille cachée « Statuts »
        # (écrite en toutes lettres dans la règle, elle dépasserait la limite de 255 caractères d'Excel).
        if "Statuts" in self.wb.sheetnames:
            del self.wb["Statuts"]
        st = self.wb.create_sheet("Statuts")
        for s in STATUTS:
            st.append([s])
        st.sheet_state = "hidden"
        L = get_column_letter(self.h["Statut"] + 1)
        ws.data_validations.dataValidation = []
        dv = DataValidation(type="list", formula1=f"Statuts!$A$1:$A${len(STATUTS)}", allow_blank=True)
        dv.add(f"{L}2:{L}2000")
        ws.add_data_validation(dv)

    def save(self):
        if commun.ESSAI:
            return
        self.mise_en_forme()
        try:
            self.wb.save(self.path)
        except PermissionError:
            alt = self.path.with_name(f"{self.path.stem}_{datetime.now():%Y%m%d_%H%M}.xlsx")
            self.wb.save(alt)
            say(f"⚠️ Tableau ouvert ailleurs : sauvegardé dans {alt.name} (à fusionner)")


def deja_contactee(o, noms, domaines, sirets):
    """Vrai si l'entreprise est déjà dans le tableau, même écrite un peu différemment
    (ex. « Xefi Lyon Est » vs « XEFI », « Lidl Villeurbanne » vs « LIDL »)."""
    n = norm(o["entreprise"])
    if not n or n in noms:
        return True
    if any(len(k) >= 4 and (k in n or n in k) for k in noms if len(n) >= 4):
        return True
    d = domaine(o.get("email") or "")
    if d and d in domaines:
        return True
    return bool(o.get("siret") and o["siret"] in sirets)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(sas|sarl|sa|eurl|sasu|groupe|group)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None
