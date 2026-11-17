"""Mise à jour du suivi d'après la messagerie (envois, réponses, non-remises) et relances.

    lecture.py     mettre_a_jour : lit la messagerie, passe chaque candidature en revue, bilan, relances dues
    envois.py      envoi constaté, relance programmée, brouillon de relance disparu
    reponses.py    adresse invalide (non-remise), réponses reçues rattachées puis classées
    classement.py  classement d'une réponse par le modèle ; réponses reconnues par leur contenu
    relance.py     écriture d'un brouillon de relance par le modèle
"""
from .classement import classer_reponse, reconnus_par_le_contenu  # noqa: F401
from .lecture import mettre_a_jour  # noqa: F401
from .relance import preparer_relance  # noqa: F401
