# -*- mode: python ; coding: utf-8 -*-
# Compilation de LMAgent.exe (dossier dist/LMAgent/) :
#     python -m PyInstaller installeur/LMAgent.spec --noconfirm
# Le .msi est ensuite fabriqué à partir de ce dossier par WiX (installeur/LMAgent.wxs).
from pathlib import Path

RACINE = Path(SPECPATH).resolve().parent

# modules chargés par le code via sys.path (PyInstaller ne les voit pas tout seul)
MODULES = [
    # alternance/src
    "candidatures", "commun", "donnees", "imap", "jours", "mails", "messagerie", "modele", "outlook",
    "pays", "rapprochement", "formulaire_lba", "formulaire_lba_chrome", "refus", "reglages", "reponses", "sites", "sources", "suivi", "tableau",
    # alternance/ (scripts appelés par lmagent)
    "alternance", "postuler", "maj_tableau", "reponses_lba",
    # web/src et web/app.py
    "api", "assistant", "auth", "chemins", "ecartees", "lettres", "pages", "parametres", "planification", "redaction", "reglages_web", "formulaire_web", "extension_lba",
    "relations", "routines", "securite", "suivi_donnees", "tour_web", "icone_tache", "app",
    # src/ (modules de la racine du projet)
    "agent", "tour", "emplacements", "version", "mise_a_jour", "boucle", "sans_fenetre",
    # dépendances chargées dynamiquement
    "win32com", "win32com.client", "pythoncom", "pywintypes", "win32timezone",
    # icône de la zone de notification
    "pystray", "pystray._win32", "PIL.Image", "PIL.PngImagePlugin",
]
# modules découpés en dossiers (src/agent/, alternance/src/tableau/…) : chacun de leurs modules, trouvé tout seul
for dossier in ("src", "alternance/src"):
    for init in sorted((RACINE / dossier).glob("*/__init__.py")):
        MODULES += [f"{init.parent.name}.{f.stem}" for f in sorted(init.parent.glob("*.py"))
                    if f.stem not in ("__init__", "__main__")]

a = Analysis(
    [str(RACINE / "lmagent.py")],
    pathex=[str(RACINE / p) for p in ("alternance/src", "alternance", "web/src", "web", "src", ".")],
    datas=[
        (str(RACINE / "web" / "templates"), "web/templates"),
        (str(RACINE / "web" / "static"), "web/static"),
        (str(RACINE / "web" / "extension"), "web/extension"),      # extension Chrome (formulaire prérempli)
        (str(RACINE / "alternance" / "donnees" / "config_alternance.example.json"), "alternance/donnees"),
        (str(RACINE / "alternance" / "donnees" / "profil.example.md"), "alternance/donnees"),
        (str(RACINE / "alternance" / "donnees" / "interdits.example.md"), "alternance/donnees"),
        (str(RACINE / "alternance" / "donnees" / "suivi_alternance.example.xlsx"), "alternance/donnees"),
        (str(RACINE / "config.example.json"), "."),
    ],
    hiddenimports=MODULES,
    excludes=["tkinter", "pytest", "IPython", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="LMAgent",
    icon=str(RACINE / "web" / "static" / "favicon.ico"),
    console=False,         # pas de fenêtre noire : icône près de l'horloge, sortie dans logs/ (voir lmagent.py)
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="LMAgent", upx=False)
