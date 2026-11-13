"""Génère le logo LMAgent (même style que MyCMS) : fond bleu nuit arrondi, serpent Python chevauché
par un badge violet (l'agent), texte « LM » en bleu et « Agent » en violet.

    python outils\\generer_logo.py

Icônes lues dans outils/logo/ (PNG à fond transparent) : python.png (obligatoire), puis
lmstudio.png et qwen.png si tu les ajoutes (placées à côté). Le badge de l'agent est dessiné ici.
Fichiers produits dans web/static/ : logo.png (256×256), logo-wide.png (bannière) et favicon.ico.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
SORTIE = ICI.parent / "web" / "static"
EN_PLUS = ["lmstudio.png", "qwen.png"]

FOND = (30, 41, 59, 255)            # bleu nuit, comme MyCMS
BLEU_LM = (75, 139, 190, 255)       # bleu clair du logo Python (#4B8BBE), lisible sur fond sombre
VIOLET_AGENT = (139, 92, 246, 255)  # violet proche de celui de LM Studio (#8B5CF6) : à ajuster si besoin
POLICES = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def police(taille):
    for p in POLICES:
        if Path(p).exists():
            return ImageFont.truetype(p, taille)
    return ImageFont.load_default()


def charger(nom, hauteur):
    f = ICI / "logo" / nom
    if not f.exists():
        return None
    im = Image.open(f).convert("RGBA")
    im = im.crop(im.getbbox())
    return im.resize((max(1, round(im.width * hauteur / im.height)), hauteur), Image.LANCZOS)


def badge(cote):
    """Losange violet arrondi avec un petit réseau de nœuds blancs (l'agent) — dessin original."""
    g = cote * 4
    im = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = int(g * 0.15)
    d.rounded_rectangle((m, m, g - m, g - m), radius=int(g * 0.12), fill=VIOLET_AGENT)
    im = im.rotate(45, resample=Image.BICUBIC)
    d = ImageDraw.Draw(im)
    c = g / 2
    noeuds = [(c - g * 0.13, c - g * 0.12), (c + g * 0.14, c - g * 0.06), (c - g * 0.02, c + g * 0.16)]
    centre = (c, c)
    epais = int(g * 0.045)
    for n in noeuds:
        d.line([centre, n], fill="white", width=epais)
    d.line([noeuds[0], noeuds[2]], fill="white", width=epais)
    for x, y in noeuds:
        r = g * 0.065
        d.ellipse((x - r, y - r, x + r, y + r), fill="white")
    r = g * 0.075
    d.ellipse((c - r, c - r, c + r, c + r), fill=VIOLET_AGENT, outline="white", width=epais)
    return im.resize((cote, cote), Image.LANCZOS)


def embleme(hauteur):
    """Serpent Python chevauché en bas à droite par le badge de l'agent (comme Git sur MyCMS),
    puis les logos LM Studio / Qwen s'ils sont fournis."""
    py = charger("python.png", hauteur)
    lm, qw = charger("lmstudio.png", int(hauteur * 0.62)), charger("qwen.png", int(hauteur * 0.82))
    if lm and qw:
        # grappe comme sur MyCMS : Python et Qwen en haut, LM Studio qui chevauche les deux en bas au centre
        ecart = int(hauteur * 0.06)
        largeur = py.width + ecart + qw.width
        out = Image.new("RGBA", (largeur, int(hauteur * 1.22)), (0, 0, 0, 0))
        out.alpha_composite(py, (0, 0))
        out.alpha_composite(qw, (largeur - qw.width, int(hauteur * 0.06)))
        out.alpha_composite(lm, ((largeur - lm.width) // 2 + int(hauteur * 0.04), out.height - lm.height))
        return out
    b = badge(int(hauteur * 0.62))
    largeur = py.width + int(b.width * 0.55)
    out = Image.new("RGBA", (largeur, int(hauteur * 1.12)), (0, 0, 0, 0))
    out.alpha_composite(py, (0, 0))
    out.alpha_composite(b, (largeur - b.width, out.height - b.height))
    autres = [i for i in (lm, qw) if i]  # un seul des deux fourni : placé à côté
    if not autres:
        return out
    ecart = int(hauteur * 0.12)
    total = out.width + sum(ecart + i.width for i in autres)
    res = Image.new("RGBA", (total, out.height), (0, 0, 0, 0))
    res.alpha_composite(out, (0, 0))
    x = out.width
    for i in autres:
        res.alpha_composite(i, (x + ecart, (out.height - i.height) // 2))
        x += ecart + i.width
    return res


def texte(draw, x, y, taille):
    f = police(taille)
    draw.text((x, y), "LM", font=f, fill=BLEU_LM)
    draw.text((x + draw.textlength("LM", font=f), y), "Agent", font=f, fill=VIOLET_AGENT)


def mesure(taille):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    return d.textlength("LMAgent", font=police(taille)), d.textbbox((0, 0), "LMAgent", font=police(taille))


def carre(cote=256, echelle=4):
    c = cote * echelle
    im = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, c - 1, c - 1), radius=int(c * 0.16), fill=FOND)
    e = embleme(int(c * 0.4))
    if e.width > c * 0.84:
        e = e.resize((int(c * 0.84), int(e.height * c * 0.84 / e.width)), Image.LANCZOS)
    im.alpha_composite(e, ((c - e.width) // 2, int(c * 0.07)))
    taille = int(c * 0.24)
    while mesure(taille)[0] > c * 0.88:
        taille -= 4
    largeur, boite = mesure(taille)
    texte(d, (c - largeur) / 2, int(c * 0.86) - boite[3], taille)
    return im.resize((cote, cote), Image.LANCZOS)


def banniere(hauteur=128, echelle=4):
    h = hauteur * echelle
    e = embleme(int(h * 0.62))
    taille = int(h * 0.46)
    l_txt, boite = mesure(taille)
    marge, ecart = int(h * 0.16), int(h * 0.12)
    largeur = marge + e.width + ecart + int(l_txt) + marge
    im = Image.new("RGBA", (largeur, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, largeur - 1, h - 1), radius=int(h * 0.2), fill=FOND)
    im.alpha_composite(e, (marge, (h - e.height) // 2))
    texte(d, marge + e.width + ecart, (h - (boite[3] - boite[1])) / 2 - boite[1], taille)
    return im.resize((largeur // echelle, hauteur), Image.LANCZOS)


if __name__ == "__main__":
    if not (ICI / "logo" / "python.png").exists():
        raise SystemExit("outils/logo/python.png introuvable")
    print("Logos en plus :", ", ".join(n for n in EN_PLUS if (ICI / "logo" / n).exists()) or "aucun")
    logo = carre()
    logo.save(SORTIE / "logo.png")
    banniere().save(SORTIE / "logo-wide.png")
    logo.save(SORTIE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("Écrit : web/static/logo.png, logo-wide.png, favicon.ico")
