"""Conversation avec le modèle (outils compris) : chat interactif, tâche automatique, ligne de commande."""
import argparse
import json
import sys
import time
import urllib.error

import agent


def chat(messages):
    c = agent.CONFIG
    req = {"model": c["modele"], "messages": messages, "tools": agent.TOOL_SCHEMAS, "temperature": 0.6}
    if not c.get("reflexion", False):
        req["reasoning_effort"] = "none"  # sans réflexion : environ 10x plus rapide
    return agent.post_chat(req)


def _executer(call):
    """Exécute un appel d'outil demandé par le modèle ; renvoie le résultat en texte (ou l'erreur)."""
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"].get("arguments") or "{}")
        agent.say(f"🔧 {name}({', '.join(f'{k}={str(v)[:80]!r}' for k, v in args.items())})")
        return str(agent.TOOLS[name][0](**args))
    except Exception as e:
        return f"Erreur : {e}"


def run_turn(messages):
    for _ in range(agent.CONFIG["etapes_max"]):
        msg = chat(messages)
        thinking = msg.get("reasoning_content") or msg.get("reasoning")
        if thinking and agent.CONFIG["afficher_reflexion"]:
            print(f"\033[90m💭 {thinking.strip()}\033[0m")

        entry = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            entry["tool_calls"] = msg["tool_calls"]
        messages.append(entry)
        if not msg.get("tool_calls"):
            return msg.get("content") or ""

        for call in msg["tool_calls"]:
            result = _executer(call)
            agent.log(f"   -> {result[:300]}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return "(limite d'étapes atteinte)"


# --- Points d'entrée -----------------------------------------------------------
def run_auto(consigne: str, nom: str):
    agent.AUTO = True
    agent.log(f"===== TÂCHE AUTO « {nom} » =====")
    agent.log(f"Consigne : {consigne}")
    agent.ensure_server()
    messages = [{"role": "system", "content": agent.system_prompt()},
                {"role": "user", "content": consigne}]
    t = time.time()
    try:
        agent.say(f"Compte rendu : {run_turn(messages)}")
    except Exception as e:
        agent.say(f"❌ Échec : {e}")
        sys.exit(1)
    agent.log(f"===== Fin ({time.time() - t:.0f} s) =====\n")


def run_chat():
    agent.ensure_server()
    print(f"🤖 Agent prêt ({agent.CONFIG['modele']})")
    print(f"   Accès : {', '.join(map(str, agent.ALLOWED))}")
    print("   /reset pour effacer la mémoire, /quit pour quitter\n")
    messages = [{"role": "system", "content": agent.system_prompt()}]
    while True:
        try:
            user = input("\033[1mToi > \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user == "/quit":
            break
        if user == "/reset":
            messages = messages[:1]
            print("Mémoire effacée.\n")
            continue
        agent.log(f"Toi > {user}")
        messages.append({"role": "user", "content": user})
        try:
            reply = run_turn(messages)
            agent.log(f"Agent > {reply}")
            print(f"\n\033[32mAgent >\033[0m {reply}\n")
        except urllib.error.URLError as e:
            print(f"❌ Erreur de connexion : {e}\n")


def main():
    ap = argparse.ArgumentParser(description="Agent IA local (LM Studio)")
    ap.add_argument("--task", help="consigne à exécuter automatiquement")
    ap.add_argument("--tache", help="nom d'un fichier taches/<nom>.txt à exécuter automatiquement")
    a = ap.parse_args()
    if a.tache:
        f = agent.TACHES / f"{a.tache}.txt"
        if not f.exists():
            agent.log(f"❌ Tâche introuvable : {f}")
            sys.exit(f"Tâche introuvable : {f}")
        run_auto(f.read_text(encoding="utf-8").strip(), a.tache)
    elif a.task:
        run_auto(a.task, "ligne de commande")
    else:
        run_chat()
