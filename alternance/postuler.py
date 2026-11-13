"""Assistant pour postuler par formulaire (La Bonne Alternance, site de l'entreprise), entreprise par entreprise.

    python alternance\\postuler.py
    python alternance\\postuler.py --reponses   (écrit seulement les réponses manquantes, sans rien ouvrir)

Pour chaque ligne « À postuler » du tableau (La Bonne Alternance ou formulaire du site de l'entreprise) :
  1. ouvre la page de l'entreprise (La Bonne Alternance, ou le formulaire de contact) dans ton navigateur ;
  2. copie la lettre (avec ta signature) dans le presse-papiers : il n'y a plus qu'à coller (Ctrl+V) ;
     les réponses aux trois questions du formulaire (motivations, missions, expériences)
     se copient avec les touches 1, 2 et 3 ;
  3. te demande ce que tu as fait, et met le tableau à jour.

La lettre vient de recherche.py (gardée dans alternance/donnees/reponses_lba.json, ou dans un ancien
brouillon « [À postuler…] » de la messagerie). S'il n'y en a pas, elle est écrite par le modèle. C'est toujours toi qui envoies le formulaire.
Ferme le tableau Excel avant de lancer.
"""
import ctypes
import re
import sys
import webbrowser
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # modules internes (alternance/src)
import commun  # noqa: E402
from commun import CFG, P  # noqa: E402
import reponses  # noqa: E402
from tableau import A_POSTULER, C_FORMULAIRE, C_LBA, LBA, Suivi  # noqa: E402


# --- Presse-papiers Windows (accents compris) -------------------------------------------
def copier(texte):
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = texte.encode("utf-16-le") + b"\x00\x00"
    h = k32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE | GMEM_ZEROINIT
    ctypes.memmove(k32.GlobalLock(h), data, len(data))
    k32.GlobalUnlock(h)
    for _ in range(10):
        if u32.OpenClipboard(None):
            break
    u32.EmptyClipboard()
    u32.SetClipboardData(13, h)  # CF_UNICODETEXT
    u32.CloseClipboard()


# --- Lettre ----------------------------------------------------------------------------
def signature():
    """Signature texte pour les formulaires (config_alternance.json → "signature_formulaire")."""
    s = CFG.get("signature_formulaire") or {}
    lignes = [s.get("nom"), s.get("titre"), s.get("telephone"), s.get("email")]
    for etiquette, cle in (("LinkedIn", "linkedin"), ("Portfolio", "portfolio"), ("GitHub", "github")):
        if s.get(cle):
            lignes.append(f"{etiquette} : {s[cle]}")
    return "\n".join(l for l in lignes if l)


def nettoyer(corps, garder_signature=False):
    """Texte du brouillon -> lettre seule (sans la ligne du lien, ni la signature Outlook).
    garder_signature=True : brouillon de mail, affiché tel qu'il partira (signature comprise)."""
    t = corps.replace("\r\n", "\n")
    t = re.sub(r"^\s*Lien pour postuler\s*:.*\n+", "", t)
    fin = t.rfind("Cordialement")
    if fin != -1 and not garder_signature:
        t = t[:fin] + "Cordialement,"
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def lettres_des_brouillons(lire_messagerie=True):
    """{lien pour postuler: texte de la lettre} depuis les brouillons « [À postuler…] »,
    et {adresse: texte} pour les candidatures par mail (clé = adresse du destinataire).
    lire_messagerie=False : seulement les lettres enregistrées (sans ouvrir la messagerie)."""
    from messagerie import ouvrir
    res = {}
    try:
        brouillons = ouvrir().textes_brouillons() if lire_messagerie else []
    except Exception:  # messagerie indisponible : on garde au moins les lettres enregistrées
        brouillons = []
    for sujet, corps, destinataires in brouillons:
        if not sujet.startswith("[À postuler"):
            for a in destinataires:
                if a:
                    res.setdefault(a.lower(), nettoyer(corps, garder_signature=True))
            continue
        m = re.search(r"Lien pour postuler\s*:\s*(\S+)", corps)
        if m:
            res[m.group(1).strip()] = nettoyer(corps)
    res.update({lien: nettoyer(t) for lien, t in reponses.lettres().items()})  # lettres sans brouillon
    return res


def ecrire_lettre(s, row):
    """Pas de brouillon : le modèle écrit la lettre (tour, sinon ce PC)."""
    from candidatures import rediger_candidature
    preparer_modele()
    o = {"entreprise": s.get(row, "Entreprise"), "poste": s.get(row, "Poste"), "lieu": s.get(row, "Lieu"),
         "contact": "", "email": "", "infos": ""}
    _, corps = rediger_candidature(o)
    lettre = nettoyer(corps)
    reponses.enregistrer_lettre((s.get(row, "Lien") or "").strip(), lettre)
    return lettre


def preparer_modele():
    import agent
    if not getattr(preparer_modele, "pret", False):
        agent.ensure_server()
        preparer_modele.pret = True


def reponses_de(s, row, deja):
    """Réponses du formulaire pour cette ligne ; écrites par le modèle si elles manquent."""
    lien = (s.get(row, "Lien") or "").strip()
    if reponses.a_des_reponses(deja.get(lien)):
        return deja[lien]
    preparer_modele()
    o = {"entreprise": s.get(row, "Entreprise"), "poste": s.get(row, "Poste"), "lieu": s.get(row, "Lieu")}
    r = reponses.rediger_reponses(o)
    reponses.enregistrer(lien, r)
    deja.setdefault(lien, {}).update(r)
    return deja[lien]


def ecrire_reponses_manquantes(s, a_faire):
    deja = reponses.lire()
    manquent = [r for r in a_faire if not reponses.a_des_reponses(deja.get((s.get(r, "Lien") or "").strip()))]
    print(f"{len(manquent)} entreprise(s) sans réponses au formulaire.")
    for row in manquent:
        print(f"   ✍️ {s.get(row, 'Entreprise')}...")
        try:
            reponses_de(s, row, deja)
        except Exception as e:
            print(f"   ❌ Impossible ({e})")
    print("✅ Terminé : les réponses sont visibles sur la page « À postuler ».")


# --- Programme -------------------------------------------------------------------------
def main():
    s = Suivi(commun.chemin_tableau())
    a_faire = [r for r in s.rows() if (s.get(r, "Statut") or "") in A_POSTULER]
    if not a_faire:
        print("Aucune candidature « À postuler » dans le tableau. 👍")
        return
    if "--reponses" in sys.argv:
        ecrire_reponses_manquantes(s, [r for r in a_faire if s.get(r, "Statut") == LBA])
        return
    deja = reponses.lire()
    sig = signature()
    if not sig:
        print("⚠️ Pas de signature : remplis \"signature_formulaire\" dans config_alternance.json.")
    elif "linkedin" not in sig.lower():
        print("ℹ️ Ajoute le lien de ton profil LinkedIn dans \"signature_formulaire\" → \"linkedin\".")
    print("📬 Lecture des lettres (et des anciens brouillons)...")
    lettres = lettres_des_brouillons()
    cv = next((P(p) for p in CFG.get("pieces_jointes", []) if "cv" in P(p).name.lower()), None)
    print(f"\n{len(a_faire)} candidature(s) à faire. Pour chacune : la page s'ouvre, la lettre est "
          "copiée, tu colles (Ctrl+V) et tu envoies.")
    if cv:
        print(f"CV à joindre si le formulaire le demande : {cv}")

    faites = 0
    for i, row in enumerate(a_faire, 1):
        ent, lien = s.get(row, "Entreprise"), (s.get(row, "Lien") or "").strip()
        print(f"\n━━ {i}/{len(a_faire)} · {ent} — {s.get(row, 'Poste') or ''} ({s.get(row, 'Lieu') or ''})")
        lettre = lettres.get(lien)
        if not lettre:
            print("   (pas de brouillon pour cette entreprise : le modèle écrit la lettre...)")
            try:
                lettre = ecrire_lettre(s, row)
            except Exception as e:
                print(f"   ❌ Impossible d'écrire la lettre ({e}) : on passe.")
                continue
        texte = lettre + ("\n\n" + sig if sig else "")
        copier(texte)
        if lien.startswith("http"):
            webbrowser.open(lien)
            print("   🌐 Page ouverte dans ton navigateur.")
        else:
            print("   ⚠️ Pas de lien dans le tableau pour cette entreprise.")
        print("   📋 Lettre copiée : colle-la dans le champ message (Ctrl+V).")
        try:
            rep = reponses.en_liste(reponses_de(s, row, deja)) if s.get(row, "Statut") == LBA else []
        except Exception as e:
            rep = []
            print(f"   ⚠️ Réponses du formulaire non écrites ({e}).")
        if rep:
            print("   Réponses du formulaire prêtes : touches 1 (motivations), 2 (missions), 3 (expériences).")
        while True:
            r = input("   [o] envoyé  [p] passer  [a] abandonner  [v] voir tout  "
                      "[c] recopier la lettre  [1-3] copier une réponse  [q] quitter > ").strip().lower()
            if r == "v":
                print("\n" + texte + "\n")
                for t, x in rep:
                    print(f"── {t}\n{x}\n")
            elif r == "c":
                copier(texte)
                print("   📋 Lettre recopiée.")
            elif r.isdigit() and 1 <= int(r) <= len(rep):
                copier(rep[int(r) - 1][1])
                print(f"   📋 Réponse copiée : {rep[int(r) - 1][0]}")
            elif r in ("o", "p", "a", "q", ""):
                break
        if r == "q":
            break
        if r == "o":
            fait = C_LBA if s.get(row, "Statut") == LBA else C_FORMULAIRE
            s.set(row, "Statut", fait)
            s.set(row, "Date envoi", date.today())
            s.set(row, "Dernière action", date.today())
            canal = "La Bonne Alternance" if s.get(row, "Statut") == LBA else "du site de l'entreprise"
            s.set(row, "Notes", f"Candidature via le formulaire {canal}. {s.get(row, 'Notes') or ''}".strip())
            faites += 1
            print(f"   ✅ Noté : {fait}.")
        elif r == "a":
            s.set(row, "Statut", "Abandonné")
            print("   Noté : Abandonné.")
        else:
            print("   Passée (elle reste à faire).")
        s.save()  # enregistré après chaque entreprise
    print(f"\n✅ {faites} candidature(s) envoyée(s) cette fois-ci. "
          "S'il reste d'anciens brouillons « [À postuler…] » pour elles, tu peux les supprimer.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu : ce qui a été répondu est enregistré.")
