"""Le tableau de suivi Excel : colonnes, statuts, lecture / écriture, détection des doublons.

    statuts.py       colonnes, statuts et leurs couleurs, anciens noms de statut
    classeur.py      le fichier Excel (Suivi) : lignes, lecture, écriture, enregistrement sans risque
    mise_en_forme.py couleurs, largeurs, liste déroulante des statuts
    texte.py         nom d'entreprise comparable, dates, ville d'une adresse
    doublons.py      entreprise déjà dans le tableau ? (plusieurs établissements du même nom permis)
"""
from .statuts import (A_POSTULER, ADRESSE_A_TROUVER, C_AUTRE, C_FORMULAIRE, C_LBA, C_LINKEDIN, COLS,  # noqa: F401
                      COLS_A_CONTACTER, FORMULAIRE, HORS_MAIL, LBA, MAIL, PAGE_A_POSTULER, STATUTS, TRANSMISE,
                      ancien_statut, statut_par_canal)
from .texte import as_date, cle_lieu, norm, ville  # noqa: F401
from .doublons import deja_contactee, retenir  # noqa: F401
from .classeur import Suivi  # noqa: F401
