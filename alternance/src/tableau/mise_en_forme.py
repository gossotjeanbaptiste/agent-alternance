"""Mise en forme du tableau à l'enregistrement : en-tête, largeurs, dates, couleur des statuts, filtres,
liste déroulante des statuts (lue dans une feuille cachée « Statuts »)."""
from .statuts import STATUTS

LARGEURS = {"Entreprise": 28, "Poste": 30, "Lieu": 18, "Lien": 30, "Contact": 22, "Email": 34,
            "Statut": 26, "Dernière réponse": 50, "Notes": 50}


def mettre_en_forme(suivi):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    ws = suivi.ws
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
    for col, i in suivi.h.items():
        L = get_column_letter(i + 1)
        ws.column_dimensions[L].width = LARGEURS.get(col, 14)
        if col.startswith("Date") or col in ("Dernière action", "Relance prévue"):
            for r in range(2, ws.max_row + 1):
                ws[f"{L}{r}"].number_format = "DD/MM/YYYY"
    for row in suivi.rows():
        st = suivi.get(row, "Statut")
        if st in STATUTS:
            row[suivi.h["Statut"]].fill = PatternFill("solid", fgColor=STATUTS[st])
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    _liste_des_statuts(suivi)


def _liste_des_statuts(suivi):
    """Liste déroulante des statuts : lue dans une feuille cachée « Statuts »
    (écrite en toutes lettres dans la règle, elle dépasserait la limite de 255 caractères d'Excel)."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    if "Statuts" in suivi.wb.sheetnames:
        del suivi.wb["Statuts"]
    st = suivi.wb.create_sheet("Statuts")
    for s in STATUTS:
        st.append([s])
    st.sheet_state = "hidden"
    L = get_column_letter(suivi.h["Statut"] + 1)
    suivi.ws.data_validations.dataValidation = []
    dv = DataValidation(type="list", formula1=f"Statuts!$A$1:$A${len(STATUTS)}", allow_blank=True)
    dv.add(f"{L}2:{L}2000")
    suivi.ws.add_data_validation(dv)
