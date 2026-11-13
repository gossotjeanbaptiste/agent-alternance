"""Jours ouvrables, jours fériés, dates et heures des relances (alternance/src/jours.py)."""
from datetime import date, datetime, timedelta

import pytest

import jours


@pytest.mark.parametrize("annee, paques", [
    (2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)),
    (2027, date(2027, 3, 28)), (2030, date(2030, 4, 21)), (2038, date(2038, 4, 25)),
])
def test_paques(annee, paques):
    assert jours._paques(annee) == paques


def test_feries_fixes_et_mobiles_2026():
    f = jours.feries(2026)
    for d in (date(2026, 1, 1), date(2026, 5, 1), date(2026, 5, 8), date(2026, 7, 14), date(2026, 8, 15),
              date(2026, 11, 1), date(2026, 11, 11), date(2026, 12, 25),
              date(2026, 4, 6),     # lundi de Pâques
              date(2026, 5, 14),    # Ascension
              date(2026, 5, 25)):   # lundi de Pentecôte
        assert d in f, d
    assert len(f) == 11


def test_feries_alsace_moselle(cfg):
    assert date(2026, 4, 3) not in jours.feries(2026)
    cfg["jours_feries_alsace"] = True
    f = jours.feries(2026)
    assert date(2026, 4, 3) in f        # Vendredi saint
    assert date(2026, 12, 26) in f      # Saint-Étienne
    assert len(f) == 13


@pytest.mark.parametrize("d, attendu", [
    (date(2026, 11, 13), True),    # vendredi
    (date(2026, 11, 14), False),   # samedi
    (date(2026, 11, 15), False),   # dimanche
    (date(2026, 11, 11), False),   # 11 novembre, mercredi férié
    (date(2026, 11, 12), True),
])
def test_ouvrable(d, attendu):
    assert jours.ouvrable(d) is attendu


def test_prochain_ouvrable():
    assert jours.prochain_ouvrable(date(2026, 11, 13)) == date(2026, 11, 13)          # inclus
    assert jours.prochain_ouvrable(date(2026, 11, 13), inclus=False) == date(2026, 11, 16)
    assert jours.prochain_ouvrable(date(2026, 11, 14)) == date(2026, 11, 16)          # samedi -> lundi
    assert jours.prochain_ouvrable(date(2026, 12, 24), inclus=False) == date(2026, 12, 28)  # saute Noël + week-end
    assert jours.prochain_ouvrable(date(2026, 12, 31), inclus=False) == date(2027, 1, 4)    # 1er janvier + week-end


def test_date_relance(cfg):
    cfg["relance_apres_jours"] = 8
    assert jours.date_relance(date(2026, 11, 13)) == date(2026, 11, 23)   # 21/11 samedi -> lundi 23
    cfg["relance_apres_jours"] = 3
    assert jours.date_relance(date(2026, 11, 9)) == date(2026, 11, 12)    # 12/11, jeudi (le 11 est férié mais pas atteint)
    assert jours.date_relance(date(2026, 11, 8)) == date(2026, 11, 12)    # 11/11 férié -> 12


def test_date_relance_toujours_un_jour_ouvrable(cfg):
    d = date(2026, 1, 1)
    for i in range(400):
        r = jours.date_relance(d + timedelta(days=i))
        assert jours.ouvrable(r)
        assert r >= d + timedelta(days=i + cfg["relance_apres_jours"])


def test_heure_aleatoire_dans_la_fenetre(cfg):
    cfg["heure_envoi_relance"], cfg["fenetre_aleatoire_minutes"] = "09:30", 15
    jour = date(2026, 11, 16)
    for _ in range(200):
        h = jours.heure_aleatoire(jour)
        assert h.date() == jour
        assert datetime(2026, 11, 16, 9, 30) <= h < datetime(2026, 11, 16, 9, 45)


def test_heure_aleatoire_autre_reglage(cfg):
    cfg["heure_envoi_relance"], cfg["fenetre_aleatoire_minutes"] = "14:05", 1
    h = jours.heure_aleatoire(date(2026, 11, 16))
    assert (h.hour, h.minute) == (14, 5)
