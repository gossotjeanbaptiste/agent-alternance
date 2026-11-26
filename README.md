<p align="center"><img src="web/static/logo.png" alt="LMAgent" width="160"></p>

# lm_agent

Agent IA local (LM Studio + Qwen3.5 9B) et routine automatique de recherche d'alternance :
candidatures et relances écrites par le modèle, déposées en **brouillon** dans **Outlook ou Gmail** (au choix),
suivi dans un tableau Excel, et une interface web locale pour tout piloter. Rien n'est jamais envoyé automatiquement.

1. [Installation](#1-installation)
2. [Utilisation](#2-utilisation)
3. [Réglages de l'agent : `config.json`](#3-réglages-de-lagent--configjson)
4. [Réglages de la routine : `config_alternance.json`](#4-réglages-de-la-routine--config_alternancejson)
5. [Ton profil et ce que tu ne veux pas dans tes mails](#5-ton-profil-et-ce-que-tu-ne-veux-pas-dans-tes-mails)
6. [Fonctionnement](#6-fonctionnement)
7. [Organisation du dépôt](#7-organisation-du-dépôt)
8. [Publier une version (installeur)](#8-publier-une-version-installeur)
9. [Ce qui n'est pas versionné](#9-ce-qui-nest-pas-versionné)

---

## 1. Installation

### Avec l'installeur (le plus simple)

1. Télécharge **`LMAgent-X.Y.Z.msi`** dans les *Releases* du dépôt et lance-le : installation pour ton compte,
   sans droits administrateur (Windows peut afficher « éditeur inconnu » : l'installeur n'est pas signé).
2. Ouvre **LMAgent** (menu Démarrer ou bureau) : crée ton compte, puis l'**assistant** te guide (deuxième PC pour
   l'IA ou non, messagerie, villes, profil, CV ; import possible d'une installation existante).
3. Installe **LM Studio** et le modèle `qwen/qwen3.5-9b` (sauf si l'IA tourne sur un deuxième PC).

Tes données vivent dans `%APPDATA%\LMAgent\` (config, tableau, profil, journaux…) : jamais touchées par les mises à
jour ni la désinstallation. Les **mises à jour s'installent toutes seules** au lancement (et toutes les 6 h), après
vérification de leur empreinte SHA-256 ; désactivable dans **Paramètres** (section Mises à jour).

### Depuis le code source

### Prérequis

- **Windows** et une messagerie au choix (voir [Messagerie : Outlook ou Gmail](#messagerie--outlook-ou-gmail)) :
  - **Outlook classique** avec ton compte configuré dedans (le nouvel Outlook ne se pilote pas par script, mais les brouillons y apparaissent aussi) ;
  - ou **Gmail** (ou toute messagerie IMAP) : aucun logiciel à installer.
- **Excel n'est pas nécessaire** : le script lit et écrit le `.xlsx` lui-même. Pour le consulter, LibreOffice Calc, Excel en ligne ou la page Suivi de l'interface suffisent (garde le format `.xlsx`).
- **Python 3** puis :
  ```bash
  pip install openpyxl pywin32 flask pillow
  ```
- **LM Studio** avec le modèle `qwen/qwen3.5-9b` (ou un autre, voir `modele`).
- Optionnel : une deuxième machine avec carte graphique (« la tour ») reliée par **Tailscale** — voir [docs/GUIDE_TOUR.md](docs/GUIDE_TOUR.md).

### Fichiers de configuration

Les fichiers réels contiennent des secrets et des données personnelles : ils **ne sont pas versionnés**.
Toutes tes données de la routine vivent dans **`alternance/donnees/`**, à côté de leurs modèles `*.example.*` :

```bash
mkdir perso
copy config.example.json perso\config.json
copy alternance\donnees\config_alternance.example.json alternance\donnees\config_alternance.json
copy alternance\donnees\profil.example.md alternance\donnees\profil.md
copy alternance\donnees\interdits.example.md alternance\donnees\interdits.md
copy alternance\donnees\suivi_alternance.example.xlsx alternance\donnees\suivi_alternance.xlsx
mkdir perso\pieces_jointes
```

Puis remplir chaque fichier (sections 3 à 5).

> Ancienne installation, avec ces fichiers directement dans `alternance/` : ils sont rangés tout seuls dans
> `alternance/donnees/` au premier lancement (et le chemin du tableau est corrigé dans la config).
> De même, `config.json`, `logs/`, `linkedin/`, `pieces_jointes/`… encore à la racine du projet sont rangés
> tout seuls dans **`perso/`** (rien n'est écrasé).

---

## 2. Utilisation

### Avec l'interface web (le plus simple)

Double-clique sur **`outils\lancer_interface.bat`**, ou dans PowerShell :
```bash
cd ~/Documents/lm_agent
python lmagent.py
```
Le navigateur s'ouvre sur **http://127.0.0.1:8765**. Pour arrêter : bouton **⏻ Quitter** en haut à droite
(ou ferme la fenêtre noire). Après une mise à jour du code, quitte et relance l'interface.

**Premier lancement** : après la création du compte, un **assistant** pose quelques questions (deuxième PC pour l'IA
ou non, messagerie, villes et jeton La Bonne Alternance, profil et signature, CV) et peut importer une installation
existante ; il reste accessible depuis Paramètres.

**Connexion** : au premier lancement, l'interface te demande de créer un identifiant et un mot de passe
(8 caractères minimum) ; ensuite, il faut se connecter (case « Rester connecté 30 jours » possible).
Bouton **Se déconnecter** en haut à droite, mot de passe modifiable dans **Paramètres**.
Mot de passe oublié : supprime `alternance/donnees/acces_interface.json`, la page de création revient.

| Page | Ce qu'on y fait |
|---|---|
| **Tableau de bord** | chiffres, graphique des envois, relances à venir |
| **Suivi** | toutes les candidatures, filtres, changement de statut |
| **À postuler** | candidatures par formulaire (La Bonne Alternance, formulaire de contact du site) : ouvrir la page, copier la lettre et, pour La Bonne Alternance, les réponses aux trois questions (motivations, missions, expériences), puis « Envoyée ». « 🧾 Ouvrir le formulaire prérempli » remplit le formulaire La Bonne Alternance dans Chrome ; **sans Chrome**, la page demande quel navigateur utiliser (Edge, Brave, Vivaldi, Opera, Opera GX : prérempli, par l'extension LMAgent installée dans ce navigateur ; Firefox ou navigateur par défaut : page ouverte, lettre copiée). Les candidatures **📧 par mail** y sont aussi : site de l'entreprise, recherche Google, « Envoyée » (statut « Candidaté (mail) », date d'envoi et relance prévue), « Abandonner » (brouillon mis à la corbeille) |
| **Routines** | lancer « Relances » / « Recherche » (« mode essai » pour tester sans rien écrire ; « passages » pour l'enchaîner N fois d'affilée, 1 par défaut) ; « mails depuis » (par défaut le lundi de la semaine) : ne relit que les mails envoyés et reçus à partir de ce jour, bien plus rapide — vide = toute la période suivie ; une relance due d'une candidature plus ancienne va quand même chercher son mail d'origine, sortie en direct |
| **Tour** | état, réveil, LM Studio, mise en veille |
| **LinkedIn** | tes relations (`perso/linkedin/Connections.csv` depuis le code) qui travaillent dans une entreprise du tableau |
| **Journal** | journaux des routines |
| **Paramètres** | signature des lettres de formulaire (avec aperçu), signature ou non sous les mails, **ce que tu ne veux pas dans tes mails**, et **tous les réglages** des deux configs (sections 3 et 4), par section, avec une aide sous chaque champ |

Sécurité : l'interface n'écoute que sur 127.0.0.1 (aucun autre appareil ne peut s'y connecter), refuse les en-têtes Host
étrangers, exige d'être connecté (mot de passe haché, jamais stocké en clair ; attente croissante après 5 essais
ratés), et chaque action exige en plus un jeton secret renouvelé à chaque démarrage. Rien n'est chargé depuis Internet.

### En ligne de commande

| Commande | Rôle |
|---|---|
| `python lmagent.py` | point d'entrée unique (= `LMAgent.exe` de la version installée) : interface ; `--routine relances|recherche|tout [--essai] [--fois N] [--depuis AAAA-MM-JJ]`, `--postuler`, `--maj-tableau`, `--agent` |
| `python alternance\relances.py` | suivi des réponses + relances en brouillon |
| `python alternance\recherche.py` | nouvelles candidatures |
| `python alternance\alternance.py` | les deux à la suite |
| `python alternance\postuler.py` | assistant de candidature par formulaire : ouvre la page, copie la lettre signée (touches 1 à 3 : réponses aux questions de La Bonne Alternance), met le tableau à jour |
| `python alternance\postuler.py --reponses` | écrit seulement les réponses aux questions qui manquent |
| `python alternance\maj_tableau.py` | met le tableau à jour d'après ta messagerie et te pose des questions (`--voir` = lecture seule) |
| `python lmagent.py --agent` | agent en chat (fichiers, PowerShell, web) |
| `python src\tour etat / reveiller / veille / eteindre / redemarrer / annuler` | pilotage de la tour |

Ajoute `--essai` aux scripts de la routine pour tout simuler sans rien écrire.

### Tests

```bash
pip install pytest
python -m pytest
```
Plus de 500 tests (dossier `tests/`, un fichier par partie du code) : outils de mails, jours fériés, tableau,
rangement des données, réglages, sites des entreprises, La Bonne Alternance, orientation des candidatures,
suivi et relances, Gmail / IMAP (faux serveur), Outlook (sans le logiciel), assistant de candidature, interface web
(protection, pages, actions, réglages), outils de fichiers de l'agent, logo.
Ils ne touchent jamais à tes données (dossier temporaire via `LMAGENT_DONNEES`), n'accèdent pas au réseau,
n'utilisent ni le modèle, ni ta messagerie, ni la tour (tout est simulé).

### Tous les jours automatiquement

```bash
.\outils\planifier.ps1 -Tache relances -Heure 10:00
.\outils\planifier.ps1 -Tache recherche -Heure 10:15
```
`-Lister` affiche les tâches, `-Supprimer` en retire une, `-Maintenant` la lance tout de suite.
Plus simple : page **Routines** → « Tous les jours automatiquement » : une routine peut être programmée **à plusieurs heures**, chacune avec son **nombre de passages** (tâches `LMAgent_<routine>_<HHMM>`, ✕ pour en supprimer une ; marche aussi avec la version installée).
Le PC doit être allumé, session ouverte.

### Avant de lancer

- **Ferme le tableau Excel** (sinon le script enregistre une copie datée à côté).
- **Avec Outlook** : l'Outlook classique s'ouvre tout seul en arrière-plan, connecte-toi s'il le demande. **Avec Gmail** : rien à ouvrir.
- **La tour** : ta session Windows doit être ouverte (en veille ou verrouillée, c'est bon). Le script la réveille, ouvre LM Studio et Tailscale si besoin, puis libère tout à la fin.
- Les brouillons arrivent dans ta messagerie : **relis et envoie-les (ou planifie-les) toi-même**.

---

## 3. Réglages de l'agent : `config.json`

### À changer obligatoirement

| Clé | Quoi mettre |
|---|---|
| `utiliser_tour` | `true` si un deuxième PC (la tour) fait tourner l'IA ; `false` : seul ce PC est utilisé et tout ce qui concerne la tour est caché (absent : déduit de `serveurs`) |
| `serveurs` | Liste des serveurs LM Studio essayés dans l'ordre. **Sans tour** : ne garder que `{"nom": "ce PC", "url": "local"}`. **Avec tour** : remplacer `nom-de-la-tour` par son nom Tailscale (ex. `http://pc-tour:1236/v1`) |
| `tour.mac` | Adresse MAC de la carte **Ethernet** de la tour (`Get-NetAdapter` sur la tour) — pour le Wake-on-LAN |
| `tour.broadcast` | Adresse de diffusion du réseau local, en général `192.168.1.255` (ou `192.168.0.255`…) |
| `tour.ssh` | `utilisateur@nom-de-la-tour` (nom du profil Windows de la tour + nom Tailscale) |
| `tour.url_lmstudio` | Même adresse que la tour dans `serveurs` |
| `tour.wol_internet.hote` | Adresse publique de ta box, pour réveiller la tour depuis l'extérieur (laisser `""` sinon). La box doit avoir le Wake-on-LAN activé, sans filtre d'adresse source |

### Selon tes envies

| Clé | Défaut | Effet |
|---|---|---|
| `ordre_ce_pc` | `["carte_dediee", "npu", "carte_integree", "processeur"]` | Sur **ce PC**, dans l'ordre : carte graphique dédiée (NVIDIA, AMD RX, Intel Arc A/B — LM Studio en CUDA ou Vulkan), **NPU Intel** des Core Ultra (OpenVINO Model Server : la carte graphique reste libre, le PC reste utilisable pendant une routine), carte graphique du processeur (Vulkan), processeur seul. Ce qui manque sur le PC est sauté ; ce qui échoue passe la main au suivant ; retirer une ligne pour ne jamais l'utiliser |
| `modele_npu` / `npu_installation_auto` | `OpenVINO/Qwen3-8B-int4-cw-ov` / `true` | Modèle du NPU, et son installation la première fois qu'il sert (OVMS et le modèle, ~5 Go une seule fois, dans `%LOCALAPPDATA%\LMAgent\openvino`) |
| `gpu` | `"auto"` | Moteur LM Studio des cartes graphiques de ce PC : NVIDIA → CUDA le plus récent, AMD / Intel → Vulkan. Forcer avec `"cuda"` ou `"vulkan"` (mesuré sur un Core Ultra 5 125H, même lettre : carte du processeur / Vulkan ≈ 45-50 s, NPU / OpenVINO ≈ 40-60 s) |
| `modele` | `qwen/qwen3.5-9b` | Identifiant du modèle dans LM Studio |
| `contexte` | `16384` | Taille du contexte (doit tenir dans la mémoire de la carte graphique) |
| `reflexion` | `false` | `true` = le modèle « réfléchit » avant de répondre : ~10× plus lent |
| `decharger_a_la_fin` | `true` | Décharge le modèle à la fin pour libérer la VRAM |
| `fermer_lmstudio_apres` / `tour.fermer_lmstudio_apres` | `true` | LM Studio est ouvert au début s'il était fermé (sur ce PC / sur la tour), et refermé à la fin — seulement si c'est le script qui l'a ouvert |
| `tour.verifier_gpu` / `vram_libre_min_mo` / `gpu_utilisation_max` | `true` / `7000` / `40` | Avant d'utiliser la tour, lit sa carte graphique (nvidia-smi par SSH) : s'il reste moins de 7000 Mo libres ou qu'elle est utilisée à plus de 40 % (un jeu, par exemple), la tour est laissée tranquille et le travail se fait sur ce PC |
| `tour.veille_apres` | `false` | `true` = remet la tour en veille à la fin, seulement si elle dormait et que le script l'a réveillée. Désactivé par défaut : tu peux utiliser la tour en même temps |
| `tour.attente_reveil_s` | `150` | Temps max d'attente du réveil de la tour |
| `tour.wol_internet.ports` | `[9, 7]` | Ports UDP du Wake-on-LAN configurés dans la box |
| `tour.ssh_lan` | `""` | SSH de la tour par le réseau local (`utilisateur@192.168.1.XX`) : sert à relancer Tailscale sur la tour s'il est coupé |
| `tour.port_serveur` / `tour.lms_tour` | `1235` / chemin de `lms.exe` | Pour démarrer le serveur LM Studio de la tour par SSH s'il est arrêté |
| `dossiers_autorises` | `["~/Downloads"]` | Dossiers où l'agent a le droit de lire / écrire (en plus de `workspace/`) |
| `powershell_en_auto` | `false` | Autorise PowerShell dans les tâches automatiques (risqué) |
| `etapes_max` | `20` | Nombre max d'actions de l'agent par demande |

Les valeurs par défaut de la rubrique `tour` (dans `src/tour/config.py`) ne servent que si elle manque dans `config.json`.

---

## 4. Réglages de la routine : `config_alternance.json`

Fichier `alternance/donnees/config_alternance.json`. **Tout se règle aussi dans la page Paramètres** de l'interface
(liste complète, valeurs par défaut et aides dans `alternance/src/reglages.py`) ; un réglage absent du fichier prend sa valeur par défaut.

Réglages plus fins, absents de la config d'exemple : longueur des relances et des réponses (`redaction.longueur_relance`,
`redaction.longueur_reponses`), intitulés et consignes des trois questions La Bonne Alternance (`redaction.questions`),
sites ignorés, mots des pages contact, pages essayées et pages lues par site (`sites.*`), messageries grand public et
débuts d'adresse génériques (`adresses.*`), chemins d'Outlook et délais (`outlook.*`), cache de la page À postuler et
passages max (`interface.*`).

### À changer obligatoirement

| Clé | Quoi mettre |
|---|---|
| `la_bonne_alternance.jeton_api` | Ton jeton API gratuit : créer un compte sur **api.apprentissage.beta.gouv.fr**. Vide = source ignorée |
| `la_bonne_alternance.villes` | Points de recherche `{"nom", "lat", "lon"}` (coordonnées sur geo.api.gouv.fr ou Google Maps) |
| `pieces_jointes` | Chemins de ton CV et de ton calendrier d'alternance (à mettre dans `perso/pieces_jointes/` depuis le code) |
| `tableau_suivi` | Chemin du tableau Excel ; vide = `suivi_alternance.xlsx` dans le dossier de données (créé automatiquement ; modèle : `suivi_alternance.example.xlsx`, 4 lignes fictives) |
| `signature_formulaire` | Ton nom, titre, téléphone, mail, LinkedIn, portfolio, GitHub : signature des lettres de formulaire (réglable aussi dans **Paramètres**) ; le nom sert aussi à l'objet par défaut d'une relance |
| `debut_signature` | 1re ligne de ta signature de mail (ex. `"Prénom NOM"`) : elle est retirée du mail d'origine relu avant d'écrire une relance |
| `domaines_ignores` | Domaines de ton école / employeur (ex. `["mon-ecole.fr"]`) : leurs mails ne sont jamais comptés comme des réponses d'entreprise |

### Selon tes envies

| Clé | Défaut | Effet |
|---|---|---|
| `mails_par_jour` | `5` | Nouvelles candidatures par lancement |
| `relance_apres_jours` | `8` | Délai avant une relance |
| `relances_max` | `2` | Relances max par entreprise |
| `relances_max_par_jour` | `5` | Plafond de relances par lancement |
| `heure_envoi_relance` / `fenetre_aleatoire_minutes` | `09:30` / `15` | Heure conseillée pour la relance (entre 9h30 et 9h44, prochain jour ouvrable) : affichée dans le journal et le tableau, à planifier toi-même (nouvel Outlook : Envoyer → Planifier l'envoi ; Gmail : flèche à côté d'Envoyer → Programmer l'envoi) |
| `jours_feries_alsace` | `false` | Ajoute le Vendredi saint et le 26 décembre |
| `messagerie.type` | `"outlook"` | `"outlook"` ou `"imap"` (Gmail…) : voir ci-dessous |
| `ajouter_signature` | `false` | `true` : ta signature est mise sous chaque brouillon (candidature et relance) : le fichier `signature_html` s'il est indiqué, sinon celle construite depuis `signature_formulaire`. Réglable aussi dans **Paramètres**. Laisse `false` si ta messagerie l'ajoute déjà (sinon elle apparaît deux fois) |
| `signature_html` | — | Avec `ajouter_signature` à `true` : chemin de ta signature Outlook (`%APPDATA%\Microsoft\Signatures\…htm`) |
| `reflexion` | `false` | Comme dans `config.json` |
| `la_bonne_alternance.codes_rome` | informatique | Métiers recherchés ([codes ROME](https://www.francetravail.fr)) |
| `la_bonne_alternance.rayon_km` | `25` | Rayon autour de chaque ville |
| `la_bonne_alternance.naf_acceptes` | informatique (62, 58.2, 26.x…) | Candidatures spontanées : seulement ces activités (codes NAF, un préfixe suffit). Écarte boutiques, bureautique, électricité, déchets… Les vraies offres ne sont pas filtrées. Les entreprises écartées sont listées à chaque passage dans `alternance/donnees/entreprises_refusees.csv` |
| `la_bonne_alternance.centre` | Lyon (exemple) | Ville de référence pour les poids |
| `la_bonne_alternance.villes_prioritaires` | Lyon, Villeurbanne (exemple) | Même poids que le centre (1), quelle que soit la distance |
| `la_bonne_alternance.demi_distance_km` / `poids_min` | `30` / `0.05` | Le poids des autres villes est divisé par 2 tous les 30 km depuis le centre (minimum 0,05). Les villes au poids fort sont interrogées en premier, plus souvent. Un `"poids"` écrit à la main sur une ville passe avant tout |
| `la_bonne_alternance.recherches_site_max` | `30` | Entreprises sans adresse dont le site est cherché et fouillé par passage (adresse mail, formulaire de contact) |
| `alertes_linkedin.expediteurs` / `jours` | LinkedIn / `3` | Lecture des alertes emploi LinkedIn reçues par mail |

### Messagerie : Outlook ou Gmail

Rubrique `messagerie`. Dans les deux cas, le script **n'envoie jamais rien** :
il lit tes mails (envois, réponses, avis de non-remise, alertes LinkedIn) et dépose des **brouillons**.

| | Outlook (`"type": "outlook"`, défaut) | Gmail / IMAP (`"type": "imap"`) |
|---|---|---|
| Logiciel nécessaire | Outlook classique (Windows) | aucun |
| Brouillons visibles dans | Outlook classique, nouvel Outlook, téléphone | Gmail (web, appli, téléphone) |
| Planifier un envoi | nouvel Outlook : Envoyer → Planifier l'envoi | Gmail : flèche à côté d'Envoyer → Programmer l'envoi |
| Relances | le mail d'origine est transféré | le mail d'origine est cité en dessous, avec ses pièces jointes |
| Signature | souvent ajoutée par Outlook lui-même : laisser `ajouter_signature: false` | Gmail n'ajoute pas sa signature aux brouillons créés par le script : mettre `ajouter_signature: true` (fichier HTML `imap.signature_html`, ou vide = signature construite depuis `signature_formulaire`) |

**Mettre Gmail en place :**
1. Active la **validation en deux étapes** sur ton compte Google.
2. Crée un **mot de passe d'application** sur https://myaccount.google.com/apppasswords (nom : `lm_agent`) et copie les 16 lettres.
3. Dans `config_alternance.json` :
   ```json
   "messagerie": {
     "type": "imap",
     "imap": {"serveur": "imap.gmail.com", "port": 993, "adresse": "toi@gmail.com",
              "mot_de_passe_app": "abcd efgh ijkl mnop", "signature_html": ""}
   }
   ```
   Ce fichier n'est pas envoyé sur GitHub. Ne mets jamais ton mot de passe Google normal.
4. Teste sans rien écrire : `python alternance\relances.py --essai`.

Autres messageries IMAP : même principe avec leur serveur (Yahoo : `imap.mail.yahoo.com`, OVH, Orange, Free…).
Les comptes **Microsoft** (Outlook.com / Hotmail, et les comptes professionnels ou scolaires Microsoft 365)
refusent l'IMAP par mot de passe : garde Outlook pour eux.

Les relances que tu programmes dans Gmail sont reconnues (statut « Relance programmée »), puis « Relancé »
une fois parties. Avec une autre messagerie IMAP, qui ne montre pas les mails programmés, une relance qui quitte
les Brouillons sans être encore envoyée est supposée programmée ; si tu l'as supprimée, `python alternance\maj_tableau.py` corrige la ligne.

Si Office est installé ailleurs que d'habitude, indique le chemin d'`OUTLOOK.EXE` dans Paramètres (section Messagerie, `outlook.chemins_exe`).

---

## 5. Ton profil et ce que tu ne veux pas dans tes mails

**`alternance/donnees/profil.md`** guide l'écriture des mails : identité, formation, rythme, dates, postes visés, zone,
projets à mettre en avant, style souhaité, et **un exemple de mail qui te plaît** (le plus efficace
pour obtenir ton ton). Modèle : `profil.example.md`.

**`alternance/donnees/interdits.md`** est le « contre-prompt » : une interdiction par ligne (formules creuses, mots à bannir,
émojis…). Elles sont ajoutées **à la fin** de chaque consigne d'écriture (candidatures, relances, réponses aux questions
de La Bonne Alternance), là où le modèle les respecte le mieux. Fichier relu à chaque mail ; modifiable aussi depuis
la page **Paramètres**. Modèle : `interdits.example.md`.

---

## 6. Fonctionnement

- Le modèle tourne de préférence sur la tour : ce qui est éteint est rallumé (Tailscale, tour en veille,
  LM Studio et son serveur — ouvert dans ta session même verrouillée, puis refermé à la fin), puis chargement, travail,
  déchargement (remise en veille seulement si `veille_apres` est activé). Si elle ne répond pas, bascule sur le PC local.
- Rien n'est envoyé automatiquement : les candidatures et relances par mail arrivent en **brouillon** dans Outlook ou Gmail,
  à relire et envoyer. Les candidatures par formulaire (La Bonne Alternance, site de l'entreprise) ne créent pas de brouillon :
  leur lettre est gardée dans `alternance/donnees/reponses_lba.json` et affichée sur la page « À postuler ».
- Entreprise sans adresse : son site est cherché (domaine évident type `nom.fr`, sinon recherche web), puis ses pages
  contact / recrutement sont lues pour trouver une adresse mail ou un formulaire de contact. Adresse trouvée → brouillon
  de mail ; sinon formulaire La Bonne Alternance (seulement si sa page a un bouton « Postuler », c'est-à-dire si
  l'API donne un destinataire `recipient_id` ; sinon ce n'est qu'une fiche), ou formulaire du site (statut « À postuler (formulaire du site) »).
  Le site et le formulaire trouvés sont notés dans la colonne Notes.
- Le tableau suit les envois, réponses, adresses invalides et relances ; `maj_tableau.py` comble le reste.
- Réponses reçues par mail, classées par le modèle : « Entretien », « Réponse positive », « Refus »,
  « Candidature transmise » (« j'ai fait suivre aux RH / au service » : plus de relance, mais la réponse suivante
  est classée), « Réponse à lire » (le reste) ; un accusé de réception automatique ne change rien.
  Une réponse qui n'a pas pu être classée (modèle injoignable) est retentée au lancement suivant.
- **Candidatures faites ailleurs** (Indeed, HelloWork, LinkedIn, La Bonne Alternance, site d'une entreprise) :
  leurs accusés de réception et réponses reçus par mail complètent le tableau. Entreprise absente → nouvelle ligne
  « Candidaté (…) » (source = la plateforme), seulement si le poste est de l'informatique (réglage « Mots d'un poste
  en informatique » : écarte « Serveur H/F »…) ; « À postuler » → « Candidaté » à la date du mail ; refus, entretien…
  classés. Formats d'Indeed, HelloWork, LinkedIn et La Bonne Alternance lus directement, les autres par le modèle.
  Les mails lus sont notés dans `alternance/donnees/mails_candidatures.json` (une ligne supprimée n'est pas rajoutée).
  Désactivable dans Paramètres → « Candidatures faites ailleurs ».
- Statuts d'une candidature envoyée, selon le canal : « Candidaté (mail) » (suivie et relancée automatiquement),
  « Candidaté (La Bonne Alternance) », « Candidaté (formulaire du site) », « Candidaté (LinkedIn) », « Candidaté (autre canal) ».
  Les anciens « Envoyé » et « Candidaté (hors mail) » sont convertis automatiquement (d'après les notes).
  La liste déroulante d'Excel lit ses statuts dans une feuille cachée « Statuts ».

---

## 7. Organisation du dépôt

```
lm_agent/
├── lmagent.py                 point d'entrée unique (interface, routines…) ; devient LMAgent.exe
├── config.example.json        modèle de config.json (réglages de l'agent)
├── src/                       agent IA (LM Studio, journal), tour, emplacements, mises à jour, version
├── alternance/
│   ├── relances.py, recherche.py, alternance.py, postuler.py, maj_tableau.py   scripts à lancer
│   ├── donnees/               tes données (non versionnées) + leurs modèles *.example.*
│   └── src/                   modules internes de la routine
├── web/
│   ├── app.py                 interface web (http://127.0.0.1:8765)
│   ├── src/                   pages, actions, lecture du tableau…
│   └── templates/, static/    HTML, style et JavaScript
├── outils/                    lancer_interface.bat, planifier.ps1, génération du logo
├── installeur/                compilation de LMAgent.exe et de l'installeur .msi
├── docs/                      GUIDE_TOUR.md (installer la tour)
├── tests/                     suite de tests (python -m pytest)
└── perso/                     tes fichiers quand l'appli est lancée depuis le code (non versionné) :
                               config.json, linkedin/, pieces_jointes/, logs/, workspace/, corbeille/, taches/
```

| Module (`alternance/src/` ; un nom finissant par `/` est un dossier de petits modules) | Rôle |
|---|---|
| `commun.py` | réglages partagés (config, profil, contre-prompt, mode essai) |
| `reglages.py` | liste de tous les réglages modifiables (valeurs par défaut, aides) ; lue par le code et la page Paramètres |
| `donnees.py` | emplacement des données personnelles (`alternance/donnees/`), rangement automatique des anciens fichiers |
| `jours.py` | jours ouvrables, fériés, heure d'envoi des relances |
| `modele.py` | appels au modèle IA |
| `mails.py` | outils sur les adresses et le texte |
| `tableau/` | tableau de suivi Excel (colonnes, statuts, doublons) |
| `messagerie.py` | choix de la messagerie (réglage `messagerie.type`) |
| `outlook.py` | Outlook classique : lecture, brouillons, boîte d'envoi |
| `imap/` | Gmail / IMAP : lecture, brouillons déposés sur le serveur |
| `suivi/` | mise à jour du suivi et relances ; candidatures faites ailleurs (`ailleurs.py`) |
| `sources.py` | liste « À contacter », alertes LinkedIn, La Bonne Alternance |
| `candidatures.py` | choix et rédaction des nouvelles candidatures |
| `sites/` | site des entreprises : le trouver, y chercher une adresse ou un formulaire de contact |
| `reponses.py` | candidatures par formulaire : lettre et réponses aux questions |
| `refus.py` | liste des entreprises écartées par le filtre d'activité |

Les modules de l'interface (`web/src/`) sont décrits dans l'en-tête de `web/app.py`.

---

## 8. Publier une version (installeur)

```bash
git tag v1.2.0
git push origin v1.2.0
```
Sur le dépôt public, GitHub Actions (`.github/workflows/publier.yml`) lance les tests, compile `LMAgent.exe`
(PyInstaller, `installeur/LMAgent.spec`), fabrique `LMAgent-1.2.0.msi` (WiX, `installeur/LMAgent.wxs`) et son
empreinte `.sha256`, puis crée la version GitHub : les installations existantes s'y mettent à jour seules.
Compilation locale de l'exe : `python -m PyInstaller installeur/LMAgent.spec --noconfirm` (dossier `dist/LMAgent/`).
Essai sans publier : onglet *Actions* → « Publier une version » → *Run workflow* (installeur en artefact).

## 9. Ce qui n'est pas versionné

Tout `perso/` (config.json, LinkedIn, CV, journaux…), tout `alternance/donnees/` sauf les modèles `*.example.*`
(config, profil, contre-prompt, tableau, lettres et réponses, liste des refus), CV / PDF — voir `.gitignore`.
La version installée garde tout dans `%APPDATA%\LMAgent\`.
