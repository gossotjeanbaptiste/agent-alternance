# AGENTS.md — repères pour les assistants de code

Agent IA local (LM Studio + Qwen3.5 9B) et routine de recherche d'alternance : candidatures et relances
écrites par le modèle, déposées en **brouillon** (Outlook classique ou Gmail/IMAP), suivi dans un tableau Excel,
interface web locale (Flask). Distribué aussi en version installée (`LMAgent.exe` + installeur `.msi`, mises à jour
automatiques). Le mode d'emploi complet est dans `README.md` ; ce fichier dit comment travailler dans le dépôt et
où en est le projet.

## Règles à respecter

- **Ne jamais envoyer de mail** : le script ne fait que des brouillons. Pas d'envoi différé posé par le script non plus
  (l'utilisateur planifie lui-même dans le nouvel Outlook ou Gmail).
- **Français** partout : code, commentaires, messages, journal, README, commits.
- **Petits fichiers** : un module par sujet ; à la racine seulement `lmagent.py` (point d'entrée), les modules
  généraux dans `src/` ; les scripts à lancer à la racine de `alternance/`, les modules internes dans
  `alternance/src/` ; dans `web/`, seul `app.py` à la racine, le reste dans `web/src/`. Viser **moins de ~150 lignes**
  par fichier : un sujet qui grossit devient un **dossier** (paquet Python) de petits modules, sous le même nom
  (`src/agent/`, `src/tour/`, `alternance/src/imap/`, `sites/`, `suivi/`, `tableau/`). Son `__init__.py` ré-exporte
  tout ce que le reste du code utilise : `import tableau`, `agent.CONFIG`, `suivi.mettre_a_jour` marchent comme avant.
- **Paquets avec un état partagé** (`agent`, `tour`, `sites`) : l'état vit dans `__init__.py`, et les modules du paquet
  le lisent **et s'appellent entre eux** par le paquet (`agent.CONFIG`, `agent._api(...)`, `tour.ps_distant(...)`,
  `sites._lire(...)`), jamais par une copie locale : un test remplace ainsi une valeur ou une fonction à un seul
  endroit (`monkeypatch.setattr(agent, "_api", ...)`). Dans `imap`, `suivi`, `tableau`, imports relatifs simples ;
  pour simuler le modèle dans `suivi`, remplacer `llm_json` / `llm` dans `suivi.classement` / `suivi.relance`.
- **Deux branches à garder synchronisées** : `main` (avec « la tour », PC distant à carte graphique, via Tailscale/SSH/
  Wake-on-LAN) et `local-simple` (100 % local : pas de `src/tour/`, pas de `docs/GUIDE_TOUR.md`, pas de page Tour).
  Tout changement pertinent va sur les deux (commit sur `main`, puis cherry-pick sur `local-simple`). Le `README.md`
  et, dans `src/agent/`, `__init__.py`, `serveur.py` et `liberation.py` diffèrent entre les branches : en cas de conflit, garder la version de la branche et y réappliquer
  la modification. Un changement qui ne concerne que la tour reste sur `main`.
- **Récupérer avant de travailler** (`git fetch`) : un autre PC pousse aussi sur les deux branches.
- **Aucun secret ni donnée personnelle dans git** : configs réelles, profil, tableau, export LinkedIn, CV restent
  hors du dépôt (voir `.gitignore`). Chercher les secrets avant chaque commit. Les exemples restent génériques
  (villes d'exemple autour de Lyon ou Grenoble, `utilisateur@nom-de-la-tour`, `toi@gmail.com`…).
- **Jamais de vrais noms** : après un diagnostic sur les vraies données (tableau, mails), ne reprendre dans le code,
  les tests, les commentaires ou les messages de commit **aucun** nom d'entreprise ou de personne réelle, ni adresse :
  transposer en noms inventés (Forgeval Dev, Comptanova, Pixelo, Lambert-Morel…).
- **Tests sans effet de bord** : mode `--essai` (rien n'est écrit), copie du tableau pour tester une écriture,
  faux modèle (`llm_json` remplacé) pour tester les consignes. Ne pas faire tourner le modèle sur le processeur
  du portable ; ne pas utiliser la tour si elle est occupée (le script vérifie sa carte graphique) ; ne jamais la
  mettre en veille sans demander. Un diagnostic sur la tour ou sur la messagerie réelle se fait en lecture seule.
- **Pas de valeur en dur** : tout réglage utile à l'utilisateur est décrit dans `alternance/src/reglages.py`
  (section, libellé, type, défaut, aide), lu dans le code avec `reglages.valeur("chemin")` et modifiable dans la page
  Paramètres. Seuls les détails techniques (délais réseau, tailles de lecture, noms des statuts) restent dans le code.
- **Tests** : `python -m pytest` (dossier `tests/`, socle dans `tests/conftest.py` : données temporaires via
  `LMAGENT_DONNEES` / `LMAGENT_DOSSIER`, réseau bloqué, modèle / messagerie simulés, config remise à zéro après chaque
  test). Toute nouvelle fonction testable reçoit ses tests ; ne pas tester la tour ni la connexion au serveur
  LM Studio. **Ne committer que si toute la suite passe** (vérifier le code de sortie, pas seulement la dernière ligne).
  Les scripts JavaScript des pages sont vérifiés par Node.js (`tests/test_javascript.py`) : un seul retour à la ligne
  dans une chaîne casse tout le script d'une page.
- **Chemins** : ne jamais construire un chemin de fichier personnel à partir du dossier du code ; passer par
  `src/emplacements.py` (config, journaux, workspace, LinkedIn…) ou `donnees.chemin()` / `commun.chemin_tableau()`.
- **Enregistrements** : le tableau (`Suivi.enregistrer_sur`) et `reponses_lba.json` sont écrits à côté puis remplacés
  d'un seul coup (une routine annulée ne laisse jamais un fichier à moitié écrit) ; garder ce principe.
- **Tour facultative** : réglage `utiliser_tour` (config.json) ; désactivée, seul « ce PC » est utilisé et tout ce qui
  concerne la tour est caché (`agent.utiliser_tour()`, `tour_web.disponible()`).
- **Interface web** : uniquement sur 127.0.0.1, connexion obligatoire (`web/src/auth.py` : un seul compte,
  mot de passe haché dans `acces_interface.json` du dossier de données), jeton exigé pour chaque action. Après une
  modification du code, l'interface en cours doit être redémarrée (Quitter par l'icône ou ⏻, puis relance).
- **Remplacements de texte** : passer par l'outil Edit ou un script Python écrit dans un fichier (un heredoc bash mange
  les antislashs et casse le code Python ou les chemins Windows).

## Où est quoi

| Chemin | Contenu |
|---|---|
| `lmagent.py` | point d'entrée unique (devient `LMAgent.exe`) : interface, `--routine <nom>` (`--fois N`, `--essai`), `--postuler`, `--maj-tableau`, `--agent` ; `commande_soi()` pour se relancer ; sortie en UTF-8 ligne par ligne, dans `logs/` quand il n'y a pas de console |
| `src/emplacements.py` | où vivent les fichiers personnels : `perso/` du projet (lancé depuis le code ; les anciens fichiers de la racine y sont rangés au démarrage), `%APPDATA%\LMAgent` (version installée) ou `LMAGENT_DOSSIER` (tests) ; données de la routine dans `alternance/donnees/` (code) ou `donnees/` (installée) |
| `src/agent/` | agent en chat / tâches : état et journal (`__init__`), outils (`fichiers`, `outils`), LM Studio (`lmstudio`, `moteur` : moteur CUDA / Vulkan / processeur), choix du serveur tour puis ce PC (`serveur`), niveaux de ce PC (`local`, `materiel`), NPU Intel par OpenVINO (`npu`, `npu_installation`), déchargement et fermeture à la fin (`liberation`), chat et ligne de commande (`conversation`) |
| `src/agent/local.py`, `materiel.py`, `npu.py`, `npu_installation.py` | **ordre des machines** : (1) la tour (main), puis sur ce PC, réglage `ordre_ce_pc` : (2) carte graphique dédiée (NVIDIA, AMD RX, Intel Arc A/B ; reconnue par son nom — la carte des Core Ultra s'appelle aussi « Arc » mais est intégrée), (3) NPU Intel « AI Boost » par **OpenVINO Model Server** (`ovms.exe` sans fenêtre sur 127.0.0.1:8771, API `/v3`, prêt quand `/v2/models/<nom>/ready` répond 200 ; requête adaptée par `npu.adapter` : nom du modèle, réflexion coupée par `chat_template_kwargs`), (4) carte graphique du processeur (Vulkan), (5) processeur (`--gpu off`). Niveau absent sauté, niveau qui échoue → suivant ; en cours de route, `post_chat` bascule sur les **suivants** seulement (`agent.ECARTES`). OVMS et le modèle (~5 Go) téléchargés une fois dans `%LOCALAPPDATA%\LMAgent\openvino` (`emplacements.gros_fichiers`, empreinte d'OVMS vérifiée) ; démarrer OVMS avec `--model_path` (avec `--source_model` sans `--target_device`, il régénère le graphe et prend la carte graphique) ; arrêté à la fin d'après son numéro de processus noté (`ovms.pid`), aussi par l'annulation d'une routine |
| `src/sans_fenetre.py` | activé par `lmagent.main` : sans console (exe installé), toute commande lancée (tasklist, powershell, lms…) reçoit CREATE_NO_WINDOW — plus de terminal qui clignote pendant une routine |
| `src/chrome/` | pilotage de Google Chrome sans dépendance (protocole DevTools, client WebSocket en bibliothèque standard) : profil à part (dossier `chrome` des données), port 9333 sur 127.0.0.1, fenêtre laissée ouverte |
| `src/boucle.py` | routine en plusieurs passages : modèle et LM Studio gardés ouverts jusqu'au dernier passage (fichier d'état partagé) |
| `src/tour/` (main) | pilotage de la tour : réglages (`config`), SSH (`ssh`), LM Studio ouvert par une tâche planifiée dans la session (`lmstudio`) et diagnostic en lecture seule en cas d'échec (`diagnostic`), Tailscale / Wake-on-LAN / réveil (`reseau`), carte graphique occupée (`gpu`), veille / arrêt (`alimentation`), `python src\tour <commande>` (`cli`) ; `docs/GUIDE_TOUR.md` pour l'installer |
| `src/version.py`, `src/mise_a_jour.py` | numéro de version (remplacé par le tag à la publication) ; mises à jour automatiques de la version installée (GitHub Releases, empreinte SHA-256, `msiexec /passive` lancé par un PowerShell sans fenêtre — jamais `DETACHED_PROCESS`, qui le fait quitter sans rien faire) |
| `.github/workflows/tests.yml` | tests (Windows, Python 3.12, Node.js) sur le dépôt public à chaque envoi sur `main` / `local-simple` et sur les pull requests ; appelé d'abord par `publier.yml` (installeur fabriqué seulement s'ils passent) |
| `installeur/`, `.github/workflows/publier.yml` | `LMAgent.spec` (PyInstaller, sans console ; **ajouter chaque nouveau module à `MODULES`** ; les modules des dossiers-paquets y sont ajoutés tout seuls), `LMAgent.wxs` (WiX v5, installation par utilisateur) ; un tag `vX.Y.Z` sur le dépôt public publie l'installeur |
| `outils/` | `lancer_interface.bat`, `planifier.ps1` (tâches de l'agent), `generer_logo.py` (logo style MyCMS à partir de `outils/logo/`) |
| `alternance/relances.py`, `recherche.py`, `alternance.py` | routines : suivi + relances, nouvelles candidatures, les deux ; mode `mails` (lecture de la messagerie seulement) |
| `alternance/reponses_lba.py` | routine « Réponses La Bonne Alternance » : lettre et réponses manquantes de toutes les candidatures La Bonne Alternance |
| `alternance/postuler.py` | assistant de candidature par formulaire en ligne de commande ; fonctions réutilisées par l'interface (`ecrire_lettre`, `reponses_de`, `lettres_des_brouillons`) |
| `alternance/maj_tableau.py` | mise à jour interactive du tableau |
| `alternance/donnees/` | **données personnelles** (non versionnées) + modèles `*.example.*` versionnés : `config_alternance.json`, `profil.md`, `interdits.md` (contre-prompt), `suivi_alternance.xlsx`, `reponses_lba.json`, `entreprises_refusees.csv`, `mails_candidatures.json` (mails déjà lus par `suivi/ailleurs.py`) |
| `alternance/src/donnees.py`, `commun.py` | chemins des données (rangement des anciens fichiers) ; config, profil, contre-prompt, mode essai, signature, pièces jointes |
| `alternance/src/reglages.py` | tous les réglages modifiables (défauts, aides) ; `web/src/reglages_web.py` les affiche et les enregistre |
| `alternance/src/modele.py` | appels au modèle ; `lire_json` tolère ses erreurs de JSON (virgule en trop…), sinon redemande une fois |
| `alternance/src/messagerie.py`, `imap/` | choisit `outlook.py` (COM) ou `imap/` selon `messagerie.type` — même interface ; `imap/` : `texte`, `objets`, `connexion` (reprise si le serveur coupe), `lecture`, `brouillons` |
| `alternance/src/suivi/` | lecture de la messagerie (`lecture` : `mettre_a_jour`, `relancer=False` pour « Mails reçus », bilan) : envois et relances programmées (`envois`), non-remises et réponses (`reponses`), classement par le modèle (`classement`), brouillon de relance (`relance`), candidatures faites hors de LM Agent d'après leurs accusés / réponses (`ailleurs`, lecture des mails dans `ailleurs_lecture` : formats Indeed, HelloWork, LinkedIn, La Bonne Alternance, sinon le modèle) |
| `alternance/src/rapprochement.py` | quelle candidature un mail reçu concerne : adresse, domaine, outil à son nom (`…@entreprise.on.crisp.email`), mot distinctif du nom dans une adresse perso, sinon preuves dans le contenu (domaine, téléphone, nom + code postal) si une seule candidature correspond |
| `alternance/src/candidatures.py`, `sources.py`, `sites/` | choix des entreprises (liste perso, alertes LinkedIn, API La Bonne Alternance), site (`sites/recherche`) et contact de l'entreprise (`sites/exploration`) ; sans adresse : brouillon adressé à « Entreprise (adresse à trouver) » `<a-trouver@….invalid>` |
| `alternance/src/formulaire_lba.py`, `formulaire_lba_chrome.py`, `web/src/formulaire_web.py` | bouton « 🧾 Ouvrir le formulaire prérempli » (page À postuler, candidatures La Bonne Alternance) : données préparées (`formulaire_lba` : identité de la signature des formulaires, section de réglages « Formulaire La Bonne Alternance prérempli » : situation, début et durée du contrat, école, rythme, CV), puis « Candidature simplifiée » remplie par l'extension (Chrome habituel) ou par `formulaire_lba_chrome` (Chrome à part piloté, qui exécute `web/extension/remplir.js`) ; **jamais de clic sur l'envoi** (l'utilisateur relit et envoie) |
| `web/extension/`, `web/src/extension_lba.py` | extension Chrome LMAgent (manifest V3) : remplit le formulaire La Bonne Alternance dans le **Chrome habituel** (réglage « Ouvrir le formulaire dans », par défaut). Sécurité à garder : aucune permission (ni cookies, ni onglets), script de page sur le seul site La Bonne Alternance, données remises **une fois** contre un jeton aléatoire valable 2 min passé dans l'adresse (`#lmagent=<port>.<jeton>`, effacé par l'extension), point d'entrée `/api/extension/<jeton>` réservé à l'origine de l'extension (identifiant fixe tiré de la clé du manifest) ; `remplir.js` est le seul code de remplissage, partagé avec le mode « Chrome à part » ; jamais de clic sur l'envoi. Dossier copié dans les données (`extension_chrome/`) pour un chemin stable ; bouton « Installer » de la page À postuler |
| `alternance/src/pays.py` | sites d'entreprises en France seulement (extension, sinon code postal / ville / téléphone / SIRET dans les pages) ; réglage `sites.verifier_france` |
| `alternance/src/reponses.py`, `refus.py` | lettres et réponses des formulaires (réponses pour **toute** candidature La Bonne Alternance, spontanée comprise) ; liste des entreprises écartées (raison, site, décision) |
| `alternance/src/tableau/` | tableau Excel (`classeur` : `Suivi`, `mise_en_forme`), statuts et couleurs (`statuts`), doublons (`doublons`, `texte`) (même SIRET, domaine, ou nom **et** ville : plusieurs établissements du même nom permis), `PAGE_A_POSTULER` |
| `web/app.py`, `web/src/`, `web/templates/` | interface : tableau de bord, Suivi (avec formulaire d'ajout), À postuler, Écartées, Routines, Tour, LinkedIn, Journal, Paramètres |
| `web/src/lettres.py`, `redaction.py` | cartes de la page À postuler (lettres, réponses, adresses à trouver) ; bouton « Écrire ce qui manque » (modèle puis déchargement) |
| `web/src/vers_lba.py`, `alternance/src/lba_recherche.py` | bouton « 🎓 Postuler par La Bonne Alternance » des « adresse à trouver » : fiche connue (venues de La Bonne Alternance), sinon (liste perso…) entreprise cherchée au clic par son SIRET (Notes), sinon son nom, parmi les recruteurs à 1 km de son adresse (Base Adresse Nationale), gardée seulement avec un `recipient_id` ; lien et activité notés ; lettre du brouillon gardée (`reponses_lba.json`), statut « À postuler (La Bonne Alternance) », brouillon à la corbeille, puis « Écrire ce qui manque » (réponses aux questions) |
| `web/src/ecartees.py` | page « Écartées » : raison, site / Google, « Candidater quand même » (feuille « À contacter »), « Abandonner », « Remettre » ; candidatures faites retirées |
| `web/src/routines.py`, `planification.py` | lancement d'une routine en arrière-plan, bouton « Annuler » (arbre de processus, puis modèle déchargé) ; routines quotidiennes via le Planificateur de tâches (`LMAgent_<routine>`) |
| `web/src/icone_tache.py`, `veille_tour.py` | icône près de l'horloge (pystray) : Ouvrir / Quitter LMAgent ; **quitté par l'utilisateur** (icône, bouton ⏻, Ctrl+C : `quitter(par_l_utilisateur=True)`), la tour est remise en veille (réglage `tour.veille_en_quittant`, lu dans config.json au moment de quitter) — jamais pour une fermeture de mise à jour automatique (`par_l_utilisateur=False` par défaut), ni pendant une routine, ni si la carte graphique de la tour est occupée, ni si elle est injoignable |
| `web/src/assistant.py` | assistant de premier lancement (tour oui/non, messagerie, villes, profil, CV, import d'une installation existante, `perso/` compris) |
| `web/static/tri.js`, `filtres.js` | tri, recherche et filtres des pages À postuler et Écartées (testés par Node.js) ; recherche et filtres **retenus** dans le navigateur pour chaque page (`retenirChamps`, Suivi compris : un rechargement ne les efface plus), bouton « Effacer les filtres » ; bouton « 🔄 Recharger » des trois pages (`recharger()` dans `app.js` : `?frais=1`, qui relit aussi les lettres de la page À postuler sans attendre la fin du cache) |
| `config.json` | réglages de l'agent et de la tour (non versionné, dans `perso/` ou AppData ; modèle `config.example.json`) |

## Fonctionnement en bref

- **Statuts** : « Brouillon », « Brouillon (adresse à trouver) », « À postuler (La Bonne Alternance) »,
  « À postuler (formulaire du site) », puis « Candidaté (mail) » (suivi et relances automatiques),
  « Candidaté (La Bonne Alternance / formulaire du site / LinkedIn / autre canal) » (réponses suivies, sans relance),
  « Relance en brouillon », « Relance programmée », « Relancé », réponses (« Entretien », « Réponse positive »,
  « Refus », « Candidature transmise » : suivie sans relance, « Réponse à lire »)… Liste dans `tableau/statuts.py` ; Excel la
  lit dans une feuille cachée « Statuts » (limite de 255 caractères d'une liste écrite en dur).
- **Candidature** : adresse mail trouvée (site en France) → brouillon de mail ; sinon formulaire La Bonne Alternance
  **seulement si** l'API donne un `recipient_id` (bouton « Postuler ») ; sinon formulaire de contact du site ; sinon
  « adresse à trouver ». Les candidatures par formulaire ne créent **pas** de brouillon : lettre et réponses dans
  `reponses_lba.json`.
- **Filtre d'activité** : candidatures spontanées limitées aux codes NAF informatiques (`naf_acceptes`) ; les
  entreprises écartées sont notées dans `entreprises_refusees.csv` et traitées dans la page Écartées.
- **Consignes du modèle** : profil (`profil.md`) au début, contre-prompt (`interdits.md`) à la fin, relu à chaque mail.
  Règle `reponses.NE_PAS_INVENTER` dans toute lettre et toute réponse : secteur, produits, clients seulement d'après les infos données (activité NAF notée « Activité : … » dans Notes et redonnée par `reponses.infos_du_tableau`), rien déduit du nom, nom jamais commenté (« m'inspire »…).
  La taille de l'entreprise n'est volontairement pas donnée au modèle.
- **Routines** (page Routines, planifiables) : Relances, Recherche, Les deux, Mails reçus (lecture seule de la
  messagerie, sans relance), Réponses La Bonne Alternance. Lancées par `lmagent --routine <nom> [--fois N]` dans un
  processus séparé ; plusieurs passages = une boucle qui relance des processus neufs (journal commun dans
  `logs/web_…`, écrit en temps réel, modèle gardé chargé entre les passages) ; annulables depuis la page.
- **Pièces jointes** : `commun.pieces_jointes()` ne renvoie que les fichiers qui existent ; un chemin cassé
  (config d'un autre PC) est cherché par son nom dans `pieces_jointes/`, sinon signalé dans le journal.
- **Messagerie** : Outlook classique par COM (le nouvel Outlook n'a pas d'API ; Microsoft Graph refusé par le tenant
  de l'école) ou Gmail par IMAP (mot de passe d'application ; mails programmés trouvés avec `X-GM-RAW "in:scheduled"`,
  reconnexion automatique, lecture des brouillons en une requête sans les pièces jointes).
- **Version installée** : l'exe n'a pas de console (icône près de l'horloge) ; il se met à jour seul au démarrage
  et toutes les 6 h (fenêtre de progression de Windows), sauf si le réglage est coupé ; c'est la version installée
  qui installe la suivante, donc une correction de la mise à jour ne vaut qu'à partir de la version d'après.

## Où on en est (17/11/2026)

Fait et en service : version installée 1.2.1 (installeur, mises à jour automatiques, icône), routines (dont Mails
reçus et Réponses La Bonne Alternance, annulables, planifiables), pages À postuler / Écartées (tri, recherche,
filtres, bouton « Écrire ce qui manque », formulaire La Bonne Alternance prérempli dans Chrome), formulaire d'ajout dans Suivi, sites en France seulement, réponses
rattachées même depuis un outil de support, une adresse perso ou d'après la signature, diagnostic de LM Studio sur
la tour, racine du dépôt rangée (`src/`, `outils/`, `docs/`, `perso/`), plus de terminal qui clignote pendant
une routine (`src/sans_fenetre.py`), gros fichiers découpés en dossiers de petits modules (`agent`, `tour`, `imap`,
`sites`, `suivi`, `tableau`), ordre des machines tour → carte dédiée → NPU Intel (OpenVINO) → carte du processeur
→ processeur (mesuré sur un Core Ultra 5 125H : NPU ≈ 8 jetons/s, carte du processeur ≈ 8-12 jetons/s ; le NPU
laisse le PC utilisable).

Pistes ouvertes, non demandées :
- exceptions au filtre d'activité (éditeurs de logiciels déclarés comme commerces, réparation d'ordinateurs 95.11Z) ;
- mettre à jour le dépôt public (voir ci-dessous) après chaque série de changements, sur demande.

## Dépôt public

Une copie anonymisée existe sur un dépôt public (remote `public`), branches `main` et `local-simple`, **sans
historique privé** : chaque publication est un nouveau commit (`git commit-tree <branche>^{tree} -p public/<branche>`)
avec un message rédigé pour l'occasion. Ne publier **que sur demande**, après avoir vérifié les deux arborescences
(aucun nom, école, ville réelle, IP, nom de machine, identifiant ni secret, aucun nom d'entreprise ou de personne
tiré des données ; seuls les modèles `*.example.*` de `alternance/donnees/`). Une version se publie avec un tag
`vX.Y.Z` poussé sur `public` : le workflow fabrique l'installeur (vérifier ensuite sa taille, ~18 Mo).
