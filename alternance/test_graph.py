"""
Test de connexion à Microsoft Graph (nouvel Outlook), en LECTURE SEULE.

    python alternance\\test_graph.py

La première fois : un code s'affiche, à saisir sur https://microsoft.com/devicelogin avec ton compte professionnel ou scolaire.
Ensuite le jeton est gardé dans alternance/graph_jeton.json (exclu de Git) : plus besoin de te reconnecter.
"""
import json
import sys
import urllib.request
from pathlib import Path

import msal

ICI = Path(__file__).resolve().parent
CFG = json.loads((ICI / "config_alternance.json").read_text(encoding="utf-8"))["graph"]
CACHE_FICHIER = ICI / "graph_jeton.json"
DROITS = ["Mail.ReadWrite"]  # pas Mail.Send : le script ne peut pas envoyer


def jeton():
    cache = msal.SerializableTokenCache()
    if CACHE_FICHIER.exists():
        cache.deserialize(CACHE_FICHIER.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(CFG["client_id"], token_cache=cache,
                                       authority=f"https://login.microsoftonline.com/{CFG['tenant_id']}")
    res = None
    comptes = app.get_accounts()
    if comptes:
        res = app.acquire_token_silent(DROITS, account=comptes[0])
    if not res:
        flux = app.initiate_device_flow(scopes=DROITS)
        if "user_code" not in flux:
            sys.exit(f"Impossible de démarrer la connexion : {flux.get('error_description', flux)}")
        print(flux["message"], flush=True)  # « Pour vous connecter, ouvrez ... et entrez le code ... »
        res = app.acquire_token_by_device_flow(flux)
    if "access_token" not in res:
        sys.exit(f"Connexion refusée : {res.get('error')} — {res.get('error_description', '')[:400]}")
    if cache.has_state_changed:
        CACHE_FICHIER.write_text(cache.serialize(), encoding="utf-8")
    return res["access_token"]


def graph(chemin, tok):
    req = urllib.request.Request("https://graph.microsoft.com/v1.0" + chemin,
                                 headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    tok = jeton()
    moi = graph("/me?$select=displayName,mail", tok)
    print(f"\n✅ Connecté : {moi.get('displayName')} <{moi.get('mail')}>")
    br = graph("/me/mailFolders/drafts/messages?$top=5&$orderby=lastModifiedDateTime desc"
               "&$select=subject,toRecipients,lastModifiedDateTime", tok)
    print("5 derniers brouillons :")
    for m in br.get("value", []):
        a = ", ".join(r["emailAddress"]["address"] for r in m.get("toRecipients", []))
        print(f"  {m['lastModifiedDateTime'][:16]}  {a or '(sans destinataire)'}  |  {m['subject'][:60]}")
