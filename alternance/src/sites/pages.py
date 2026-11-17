"""Lecture d'une page web (comme un navigateur) et domaine d'une adresse de site."""
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept-Language": "fr-FR,fr;q=0.9"}


def _lire(url, maxi=500_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        if "html" not in (r.headers.get("Content-Type") or "html"):
            return "", r.geturl()
        return r.read(maxi).decode("utf-8", errors="replace"), r.geturl()


def _racine(url):
    u = urllib.parse.urlparse(url if url.startswith("http") else "https://" + url)
    return re.sub(r"^www\.", "", u.netloc.lower())
