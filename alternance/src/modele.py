"""Appels au modèle IA (via agent.post_chat : bon serveur, bascule automatique)."""
import ast
import json
import re

from commun import CFG, agent

ESSAIS_JSON = 2   # une réponse au JSON illisible est redemandée une fois


def llm(prompt, system="Tu es un assistant qui aide un étudiant dans sa recherche d'alternance. Réponds en français.",
        temperature=0.7):
    req_body = {"model": agent.CONFIG["modele"], "temperature": temperature, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    if not CFG.get("reflexion", False):
        # Qwen3.5 « réfléchit » des milliers de mots avant chaque réponse : x10 sur le temps.
        req_body["reasoning_effort"] = "none"
    # passe par agent.post_chat : tour d'abord, bascule sur ce PC si elle lâche en cours de route
    return (agent.post_chat(req_body).get("content") or "").strip()


def lire_json(txt):
    """JSON d'une réponse du modèle, en tolérant ses erreurs habituelles : bloc ```json, texte autour,
    virgule avant } ou ], retour à la ligne dans un texte, guillemets typographiques, apostrophes autour des clés.
    Lève ValueError (avec un extrait) si la réponse reste illisible."""
    t = re.sub(r"^```(json)?|```$", "", (txt or "").strip(), flags=re.M).strip()
    m = re.search(r"[\[{][\s\S]*[\]}]", t)
    t = m.group(0) if m else t
    essais = [t]
    sans_virgule = re.sub(r",\s*([}\]])", r"\1", t)                     # { "a": "x", }  ->  { "a": "x" }
    essais.append(sans_virgule)
    essais.append(sans_virgule.replace("“", '"').replace("”", '"').replace("„", '"'))
    for e in essais:
        try:
            return json.loads(e, strict=False)                          # strict=False : retours à la ligne permis
        except ValueError:
            pass
    try:                                                                # {'a': 'x'} : syntaxe Python
        v = ast.literal_eval(sans_virgule)
        if isinstance(v, (dict, list)):
            return v
    except (ValueError, SyntaxError):
        pass
    extrait = " ".join(t.split())[:200]
    raise ValueError(f"réponse du modèle illisible (JSON invalide) : « {extrait}… »")


def llm_json(prompt, system=None):
    consigne = prompt + "\n\nRéponds UNIQUEMENT avec du JSON valide, sans texte autour."
    erreur = None
    for _ in range(ESSAIS_JSON):
        txt = llm(consigne, *([system] if system else []))
        try:
            return lire_json(txt)
        except ValueError as e:
            erreur = e
            consigne = (prompt + "\n\nTa réponse précédente n'était pas du JSON valide. Réponds UNIQUEMENT avec du "
                        "JSON valide : clés et textes entre guillemets droits \", pas de virgule avant } ou ], "
                        "rien avant ni après.")
    raise erreur
