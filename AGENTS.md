# AGENTS.md — repères pour les assistants de code

Agent IA local (LM Studio + Qwen3.5 9B) et routine de recherche d'alternance : candidatures et relances
écrites par le modèle, déposées en **brouillon** (Outlook classique ou Gmail/IMAP), suivi dans un tableau Excel,
interface web locale (Flask). Le mode d'emploi complet est dans `README.md` ; ce fichier dit comment travailler
dans le dépôt et où en est le projet.

## Règles à respecter

- **Ne jamais envoyer de mail** : le script ne fait que des brouillons. Pas d'envoi différé posé par le script non plus
  (l'utilisateur planifie lui-même dans le nouvel Outlook ou Gmail).
- **Français** partout : code, commentaires, messages, journal, README, commits.
- **Petits fichiers** : un module par sujet ; les scripts à lancer à la racine de `alternance/`, les modules internes
  dans `alternance/src/` ; dans `web/`, seul `app.py` à la racine, le reste dans `web/src/`.
- **Deux branches à garder synchronisées** : `main` (avec « la tour », PC distant à carte graphique, via Tailscale/SSH/
  Wake-on-LAN) et `local-simple` (100 % local : pas de `tour.py`, pas de `GUIDE_TOUR.md`, pas de page Tour).
  Tout changement pertinent va sur les deux (commit sur `main`, puis cherry-pick sur `local-simple`). Le `README.md`
  diffère entre les branches : en cas de conflit, garder la version de la branche et y réappliquer la modification.
- **Récupérer avant de travailler** (`git fetch`) : un autre PC pousse aussi sur les deux branches.
- **Aucun secret ni donnée personnelle dans git** : configs réelles, profil, tableau, export LinkedIn, CV restent
  hors du dépôt (voir `.gitignore`). Chercher les secrets avant chaque commit. Les exemples restent génériques
  (villes d'exemple autour de Lyon, `utilisateur@nom-de-la-tour`, `toi@gmail.com`…).
- **Tests sans effet de bord** : mode `--essai` (rien n'est écrit), copie du tableau pour tester une écriture,
  faux modèle (`llm_json` remplacé) pour tester les consignes. Ne pas faire tourner le modèle sur le processeur
  du portable ; ne pas utiliser la tour si elle est occupée (le script vérifie sa carte graphique) ; ne jamais la
  mettre en veille sans demander.
- **Interface web** : uniquement sur 127.0.0.1, jeton exigé pour chaque action. Après une modification du code,
  l'interface en cours doit être redémarrée (⏻ Quitter puis relance).

## Où est quoi

| Chemin | Contenu |
|---|---|
| `agent.py` | agent en chat / tâches, connexion LM Studio (tour puis ce PC), choix du moteur GPU, journal (`logs/`) |
| `tour.py` (main) | réveil, veille, état de la tour ; `GUIDE_TOUR.md` pour l'installer |
| `alternance/relances.py`, `recherche.py`, `alternance.py` | routines (suivi + relances, nouvelles candidatures, les deux) |
| `alternance/postuler.py` | assistant de candidature par formulaire (La Bonne Alternance, formulaire du site) |
| `alternance/maj_tableau.py` | mise à jour interactive du tableau |
| `alternance/donnees/` | **données personnelles** (non versionnées) + modèles `*.example.*` versionnés : `config_alternance.json`, `profil.md`, `interdits.md` (contre-prompt), `suivi_alternance.xlsx`, `reponses_lba.json`, `entreprises_refusees.csv` |
| `alternance/src/donnees.py` | chemins des données ; range automatiquement les anciens fichiers de `alternance/` dans `donnees/` |
| `alternance/src/commun.py` | config, profil, contre-prompt (`interdits()`), mode essai, signature des mails |
| `alternance/src/messagerie.py` | choisit `outlook.py` (COM) ou `imap.py` selon `messagerie.type` — même interface |
| `alternance/src/suivi.py` | mise à jour du suivi, réponses, non-remises, relances |
| `alternance/src/candidatures.py`, `sources.py`, `sites.py` | choix des entreprises (liste perso, alertes LinkedIn, API La Bonne Alternance), site et contact de l'entreprise |
| `alternance/src/reponses.py`, `refus.py` | lettres et réponses des candidatures par formulaire ; liste des entreprises écartées |
| `alternance/src/tableau.py` | tableau Excel (openpyxl, Excel non nécessaire), statuts et couleurs |
| `web/app.py`, `web/src/`, `web/templates/` | interface : tableau de bord, Suivi, À postuler, Routines, Tour, LinkedIn, Journal, Paramètres |
| `config.json` | réglages de l'agent et de la tour (non versionné ; modèle `config.example.json`) |
| `linkedin/` | export LinkedIn de l'utilisateur (non versionné), lu par la page LinkedIn |

## Fonctionnement en bref

- **Statuts** : « Brouillon », « Brouillon (adresse à trouver) », « À postuler (La Bonne Alternance) »,
  « À postuler (formulaire du site) », puis « Candidaté (mail) » (suivi et relances automatiques),
  « Candidaté (La Bonne Alternance / formulaire du site / LinkedIn / autre canal) », « Relance en brouillon »,
  « Relance programmée », « Relancé », réponses… Liste dans `tableau.py` ; Excel la lit dans une feuille cachée
  « Statuts » (limite de 255 caractères d'une liste écrite en dur).
- **Candidature** : adresse mail trouvée → brouillon de mail ; sinon formulaire La Bonne Alternance **seulement si**
  l'API donne un `recipient_id` (bouton « Postuler ») ; sinon formulaire de contact du site ; sinon « adresse à trouver ».
  Les candidatures par formulaire ne créent **pas** de brouillon : lettre et réponses dans `reponses_lba.json`.
- **Filtre d'activité** : candidatures spontanées limitées aux codes NAF informatiques (`naf_acceptes`) ; les
  entreprises écartées sont notées dans `entreprises_refusees.csv`.
- **Consignes du modèle** : profil (`profil.md`) au début, contre-prompt (`interdits.md`) à la fin, relu à chaque mail.
  La taille de l'entreprise n'est volontairement pas donnée au modèle.
- **Routines depuis l'interface** : `web/src/routines.py` lance le script dans un processus séparé, enveloppé dans
  une petite boucle (`BOUCLE`) qui le relance N fois d'affilée (champ « passages », 1 à 50) ; un seul journal
  `logs/web_…_xN.txt`, la boucle continue même si l'interface est arrêtée.
- **Messagerie** : Outlook classique par COM (le nouvel Outlook n'a pas d'API ; Microsoft Graph refusé par le tenant
  de l'école) ou Gmail par IMAP (mot de passe d'application ; mails programmés trouvés avec `X-GM-RAW "in:scheduled"`,
  reconnexion automatique, lecture des brouillons en une requête sans les pièces jointes).

## Où on en est (13/11/2026)

Fait et en service : routines quotidiennes, interface web complète, Gmail ou Outlook au choix, recherche du site et
des formulaires de contact, réponses aux questions de La Bonne Alternance, contre-prompt, signature réglable
(page Paramètres), liste des refus, rangement des données dans `alternance/donnees/`.

Pistes ouvertes, non demandées :
- exceptions au filtre d'activité (éditeurs de logiciels déclarés comme commerces, réparation d'ordinateurs 95.11Z) ;
- afficher la liste des entreprises écartées dans l'interface ;
- mettre à jour le dépôt public (voir ci-dessous) après chaque série de changements, sur demande.

## Dépôt public

Une copie anonymisée existe sur un dépôt public (remote `public`), branches `main` et `local-simple`, **sans
historique** : chaque publication est un nouveau commit (`git commit-tree <branche>^{tree} -p public/<branche>`).
Ne publier **que sur demande**, après avoir vérifié les deux arborescences (aucun nom, école, ville réelle, IP,
nom de machine, identifiant ni secret ; seuls les modèles `*.example.*` de `alternance/donnees/`).
