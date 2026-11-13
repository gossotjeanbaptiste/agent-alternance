# CLAUDE.md

@AGENTS.md

## Pour Claude Code

- Répondre en français, sans jargon inutile ; résumer ce qui est vérifié et ce qui ne l'est pas.
- Avant de toucher au dépôt : `git fetch`, puis vérifier que `main` et `local-simple` ne sont pas en retard
  sur `origin` (un autre PC pousse aussi).
- Après une modification : commit sur `main`, cherry-pick sur `local-simple`, push des deux. Ne **pas** publier
  sur le dépôt public sans demande explicite.
- Remplacements de texte dans les fichiers : passer par l'outil Edit ou un script Python écrit dans un fichier.
  Un heredoc bash mange les antislashs (`\n`, `\b`, `\\`) et casse le code Python ou les chemins Windows.
- Les fichiers de `alternance/donnees/` sont des données personnelles : les lire si besoin, ne jamais les
  committer, faire une copie avant toute opération qui les déplace ou les réécrit.
- Pour tester sans effet de bord : `--essai`, copie temporaire du tableau, faux modèle. Un script lancé « pour voir »
  (ex. `postuler.py --reponses`) peut utiliser la tour et écrire de vraies données.
