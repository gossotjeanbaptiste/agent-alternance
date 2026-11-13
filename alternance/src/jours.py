"""Jours ouvrables, jours fériés français et heures d'envoi des relances."""
import random
from datetime import date, datetime, timedelta

from commun import CFG

def _paques(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = (h + l - 7 * m + 114) % 31 + 1
    return date(y, mois, jour)


def feries(y):
    p = _paques(y)
    j = {date(y, 1, 1), date(y, 5, 1), date(y, 5, 8), date(y, 7, 14), date(y, 8, 15),
         date(y, 11, 1), date(y, 11, 11), date(y, 12, 25),
         p + timedelta(days=1), p + timedelta(days=39), p + timedelta(days=50)}
    if CFG.get("jours_feries_alsace"):
        j |= {p - timedelta(days=2), date(y, 12, 26)}
    return j


def ouvrable(d):
    return d.weekday() < 5 and d not in feries(d.year)


def prochain_ouvrable(d, inclus=True):
    if not inclus:
        d += timedelta(days=1)
    while not ouvrable(d):
        d += timedelta(days=1)
    return d


def date_relance(depuis):
    return prochain_ouvrable(depuis + timedelta(days=CFG["relance_apres_jours"]))


def heure_aleatoire(jour):
    h, m = map(int, CFG["heure_envoi_relance"].split(":"))
    base = datetime(jour.year, jour.month, jour.day, h, m)
    return base + timedelta(minutes=random.randint(0, CFG["fenetre_aleatoire_minutes"] - 1),
                            seconds=random.randint(0, 59))
