"""Appels au modèle IA (via agent.post_chat : bon serveur, bascule automatique)."""
import json
import re

from commun import CFG, agent

def llm(prompt, system="Tu es un assistant qui aide un étudiant dans sa recherche d'alternance. Réponds en français."):
    req_body = {"model": agent.CONFIG["modele"], "temperature": 0.7, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    if not CFG.get("reflexion", False):
        # Qwen3.5 « réfléchit » des milliers de mots avant chaque réponse : x10 sur le temps.
        req_body["reasoning_effort"] = "none"
    # passe par agent.post_chat : tour d'abord, bascule sur ce PC si elle lâche en cours de route
    return (agent.post_chat(req_body).get("content") or "").strip()


def llm_json(prompt, system=None):
    txt = llm(prompt + "\n\nRéponds UNIQUEMENT avec du JSON valide, sans texte autour.",
              *( [system] if system else [] ))
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    m = re.search(r"[\[{][\s\S]*[\]}]", txt)
    return json.loads(m.group(0) if m else txt)
