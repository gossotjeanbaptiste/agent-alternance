# lm_agent

Agent IA local (LM Studio + Qwen3.5 9B) et routine automatique de recherche d'alternance —
**version 100 % locale** (branche `local-simple` : pas de tour, pas de SSH, pas de Tailscale) :
candidatures et relances écrites par le modèle, déposées en **brouillon** dans **Outlook ou Gmail** (au choix),
suivi dans un tableau Excel, et une interface web locale pour tout piloter. Rien n'est jamais envoyé automatiquement.

1. [Installation](#1-installation)
2. [Utilisation](#2-utilisation)
3. [Réglages de l'agent : `config.json`](#3-réglages-de-lagent--configjson)
4. [Réglages de la routine : `config_alternance.json`](#4-réglages-de-la-routine--config_alternancejson)
5. [Ton profil et ce que tu ne veux pas dans tes mails](#5-ton-profil-et-ce-que-tu-ne-veux-pas-dans-tes-mails)
6. [Fonctionnement](#6-fonctionnement)
7. [Organisation du dépôt](#7-organisation-du-dépôt)
8. [Ce qui n'est pas versionné](#8-ce-qui-nest-pas-versionné)

---

## 1. Installation

### Prérequis

- **Windows** et une messagerie au choix (voir [Messagerie : Outlook ou Gmail](#messagerie--outlook-ou-gmail)) :
  - **Outlook classique** avec ton compte configuré dedans (le nouvel Outlook ne se pilote pas par script, mais les brouillons y apparaissent aussi) ;
  - ou **Gmail** (ou toute messagerie IMAP) : aucun logiciel à installer.
- **Excel n'est pas nécessaire** : le script lit et écrit le `.xlsx` lui-même. Pour le consulter, LibreOffice Calc, Excel en ligne ou la page Suivi de l'interface suffisent (garde le format `.xlsx`).
- **Python 3** puis :
  ```bash
  pip install openpyxl pywin32 flask
  ```
- **LM Studio** avec le modèle `qwen/qwen3.5-9b` (ou un autre, voir `modele`).
- Une carte graphique est fortement conseillée (voir § 3 : le bon moteur est choisi automatiquement).

### Fichiers de configuration

Les fichiers réels contiennent des secrets et des données personnelles : ils **ne sont pas versionnés**.
Toutes tes données de la routine vivent dans **`alternance/donnees/`**, à côté de leurs modèles `*.example.*` :

```bash
copy config.example.json config.json
copy alternance\donnees\config_alternance.example.json alternance\donnees\config_alternance.json
copy alternance\donnees\profil.example.md alternance\donnees\profil.md
copy alternance\donnees\interdits.example.md alternance\donnees\interdits.md
copy alternance\donnees\suivi_alternance.example.xlsx alternance\donnees\suivi_alternance.xlsx
mkdir pieces_jointes
```

Puis remplir chaque fichier (sections 3 à 5).

> Ancienne installation, avec ces fichiers directement dans `alternance/` : ils sont rangés tout seuls dans
> `alternance/donnees/` au premier lancement (et le chemin du tableau est corrigé dans la config).

---

## 2. Utilisation

### Avec l'interface web (le plus simple)

Double-clique sur **`lancer_interface.bat`**, ou dans PowerShell :
```bash
cd ~/Documents/lm_agent
python web\app.py
```
Le navigateur s'ouvre sur **http://127.0.0.1:8765**. Pour arrêter : bouton **⏻ Quitter** en haut à droite
(ou ferme la fenêtre noire). Après une mise à jour du code, quitte et relance l'interface.

| Page | Ce qu'on y fait |
|---|---|
| **Tableau de bord** | chiffres, graphique des envois, relances à venir |
| **Suivi** | toutes les candidatures, filtres, changement de statut |
| **À postuler** | candidatures par formulaire (La Bonne Alternance, formulaire de contact du site) : ouvrir la page, copier la lettre et, pour La Bonne Alternance, les réponses aux trois questions (motivations, missions, expériences), puis « Envoyée ». Les candidatures **📧 par mail** y sont aussi : site de l'entreprise, recherche Google, « Envoyée » (statut « Candidaté (mail) », date d'envoi et relance prévue), « Abandonner » (brouillon mis à la corbeille) |
| **Routines** | lancer « Relances » / « Recherche » (« mode essai » pour tester sans rien écrire ; « passages » pour l'enchaîner N fois d'affilée, 1 par défaut), sortie en direct |
| **LinkedIn** | tes relations (`linkedin/Connections.csv`) qui travaillent dans une entreprise du tableau |
| **Journal** | journaux des routines |
| **Paramètres** | signature des lettres de formulaire (avec aperçu), signature ou non sous les mails, **ce que tu ne veux pas dans tes mails** |

Sécurité : l'interface n'écoute que sur 127.0.0.1 (aucun autre appareil ne peut s'y connecter), refuse les en-têtes Host
étrangers, et chaque action exige un jeton secret renouvelé à chaque démarrage. Rien n'est chargé depuis Internet.

### En ligne de commande

| Commande | Rôle |
|---|---|
| `python alternance\relances.py` | suivi des réponses + relances en brouillon |
| `python alternance\recherche.py` | nouvelles candidatures |
| `python alternance\alternance.py` | les deux à la suite |
| `python alternance\postuler.py` | assistant de candidature par formulaire : ouvre la page, copie la lettre signée (touches 1 à 3 : réponses aux questions de La Bonne Alternance), met le tableau à jour |
| `python alternance\postuler.py --reponses` | écrit seulement les réponses aux questions qui manquent |
| `python alternance\maj_tableau.py` | met le tableau à jour d'après ta messagerie et te pose des questions (`--voir` = lecture seule) |
| `python agent.py` | agent en chat (fichiers, PowerShell, web) |

Ajoute `--essai` aux scripts de la routine pour tout simuler sans rien écrire.

### Tous les jours automatiquement

```bash
.\planifier.ps1 -Tache relances -Heure 10:00
.\planifier.ps1 -Tache recherche -Heure 10:15
```
`-Lister` affiche les tâches, `-Supprimer` en retire une, `-Maintenant` la lance tout de suite.
Le PC doit être allumé, session ouverte.

### Avant de lancer

- **Ferme le tableau Excel** (sinon le script enregistre une copie datée à côté).
- **Avec Outlook** : l'Outlook classique s'ouvre tout seul en arrière-plan, connecte-toi s'il le demande. **Avec Gmail** : rien à ouvrir.
- **LM Studio** : pas besoin de l'ouvrir, le script le lance avec le bon moteur (CUDA, Vulkan ou CPU) puis le referme à la fin.
- Les brouillons arrivent dans ta messagerie : **relis et envoie-les (ou planifie-les) toi-même**.

---

## 3. Réglages de l'agent : `config.json`

Rien d'obligatoire : les valeurs par défaut marchent. Le modèle tourne **sur ce PC**.

| Clé | Défaut | Effet |
|---|---|---|
| `gpu` | `"auto"` | Moteur LM Studio choisi selon la carte graphique (voir ci-dessous). Forcer avec `"cuda"`, `"vulkan"` ou `"cpu"` |
| `modele` | `qwen/qwen3.5-9b` | Identifiant du modèle dans LM Studio |
| `contexte` | `16384` | Taille du contexte (doit tenir dans la mémoire de la carte graphique) |
| `reflexion` | `false` | `true` = le modèle « réfléchit » avant de répondre : ~10× plus lent |
| `decharger_a_la_fin` | `true` | Décharge le modèle à la fin pour libérer la mémoire de la carte graphique |
| `fermer_lmstudio_apres` | `true` | LM Studio est ouvert au début s'il était fermé, et refermé à la fin — seulement si c'est le script qui l'a ouvert |
| `dossiers_autorises` | `["~/Downloads"]` | Dossiers où l'agent a le droit de lire / écrire (en plus de `workspace/`) |
| `powershell_en_auto` | `false` | Autorise PowerShell dans les tâches automatiques (risqué) |
| `etapes_max` | `20` | Nombre max d'actions de l'agent par demande |

### Choix automatique du moteur (`"gpu": "auto"`)

À chaque lancement, le script regarde les cartes graphiques du PC (la carte **dédiée** passe avant la carte intégrée) :

| Carte détectée | Moteur LM Studio sélectionné |
|---|---|
| **NVIDIA** | **CUDA le plus récent compatible** (CUDA 13 → 12 → base, LM Studio vérifie le pilote). Téléchargé automatiquement s'il n'est pas installé |
| AMD Radeon | Vulkan (dernière version installée) |
| Intel Arc / Iris | Vulkan (dernière version installée) |
| aucune | CPU |

Puis le modèle est chargé **avec toutes ses couches sur la carte graphique** (`--gpu max`) et déchargé à la fin.
Pour CUDA 13, il faut un pilote NVIDIA récent : mets-le à jour si LM Studio ne propose que CUDA 12.

---

## 4. Réglages de la routine : `config_alternance.json`

Fichier `alternance/donnees/config_alternance.json`.

### À changer obligatoirement

| Clé | Quoi mettre |
|---|---|
| `la_bonne_alternance.jeton_api` | Ton jeton API gratuit : créer un compte sur **api.apprentissage.beta.gouv.fr**. Vide = source ignorée |
| `la_bonne_alternance.villes` | Points de recherche `{"nom", "lat", "lon"}` (coordonnées sur geo.api.gouv.fr ou Google Maps) |
| `pieces_jointes` | Chemins de ton CV et de ton calendrier d'alternance (à mettre dans `pieces_jointes/`) |
| `tableau_suivi` | Chemin du tableau Excel (créé automatiquement s'il n'existe pas ; modèle : `suivi_alternance.example.xlsx`, 4 lignes fictives) |
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

Si Office est installé ailleurs que d'habitude, adapte `OUTLOOK_EXE` dans `alternance/src/outlook.py`.

---

## 5. Ton profil et ce que tu ne veux pas dans tes mails

**`alternance/donnees/profil.md`** guide l'écriture des mails : identité, formation, rythme, dates, postes visés, zone,
projets à mettre en avant, style souhaité, et **un exemple de mail qui te plaît** (le plus efficace
pour obtenir ton ton). Modèle : `profil.example.md`.

**`alternance/donnees/interdits.md`** est le « contre-prompt » : une interdiction par ligne (formules creuses, mots à bannir,
émojis…). Elles sont ajoutées **à la fin** de chaque consigne d'écriture (candidatures, relances, réponses aux questions
de La Bonne Alternance), là où le modèle les respecte le mieux. Fichier relu à chaque mail ; modifiable aussi depuis
la page **Paramètres**. Modèle : `interdits.example.md`.

**`alternance/donnees/suivi_alternance.xlsx`** : Le modèle `suivi_alternance.example.xlsx` contient 4 lignes **fictives** pour voir le format :
feuille **Suivi** (une ligne par candidature, statut en liste déroulante et en couleur) et feuille
**À contacter** (les entreprises que tu y colles passent en priorité). Supprime les lignes d'exemple,
ou pars d'un fichier vide : il est créé automatiquement s'il n'existe pas.

---

## 6. Fonctionnement

- Au lancement : démarrage du serveur LM Studio, choix du moteur (CUDA / Vulkan / CPU), chargement du modèle ;
  à la fin (même en cas d'erreur ou de Ctrl+C) : déchargement du modèle.
- Rien n'est envoyé automatiquement : les candidatures et relances par mail arrivent en **brouillon** dans Outlook ou Gmail,
  à relire et envoyer. Les candidatures par formulaire (La Bonne Alternance, site de l'entreprise) ne créent pas de brouillon :
  leur lettre est gardée dans `alternance/donnees/reponses_lba.json` et affichée sur la page « À postuler ».
- Entreprise sans adresse : son site est cherché (domaine évident type `nom.fr`, sinon recherche web), puis ses pages
  contact / recrutement sont lues pour trouver une adresse mail ou un formulaire de contact. Adresse trouvée → brouillon
  de mail ; sinon formulaire La Bonne Alternance (seulement si sa page a un bouton « Postuler », c'est-à-dire si
  l'API donne un destinataire `recipient_id` ; sinon ce n'est qu'une fiche), ou formulaire du site (statut « À postuler (formulaire du site) »).
  Le site et le formulaire trouvés sont notés dans la colonne Notes.
- Le tableau suit les envois, réponses, adresses invalides et relances ; `maj_tableau.py` comble le reste.
- Statuts d'une candidature envoyée, selon le canal : « Candidaté (mail) » (suivie et relancée automatiquement),
  « Candidaté (La Bonne Alternance) », « Candidaté (formulaire du site) », « Candidaté (LinkedIn) », « Candidaté (autre canal) ».
  Les anciens « Envoyé » et « Candidaté (hors mail) » sont convertis automatiquement (d'après les notes).
  La liste déroulante d'Excel lit ses statuts dans une feuille cachée « Statuts ».

---

## 7. Organisation du dépôt

```
lm_agent/
├── agent.py                   agent IA (connexion LM Studio, choix du moteur, journal)
├── lancer_interface.bat       lance l'interface web
├── planifier.ps1              tâches planifiées Windows
├── config.json                réglages de l'agent (non versionné ; modèle config.example.json)
├── alternance/
│   ├── relances.py, recherche.py, alternance.py, postuler.py, maj_tableau.py   scripts à lancer
│   ├── donnees/               tes données (non versionnées) + leurs modèles *.example.*
│   └── src/                   modules internes de la routine
├── web/
│   ├── app.py                 interface web (http://127.0.0.1:8765)
│   ├── src/                   pages, actions, lecture du tableau…
│   └── templates/, static/    HTML, style et JavaScript
├── linkedin/                  ton export LinkedIn (non versionné)
└── pieces_jointes/, logs/     CV et calendrier, journaux (non versionnés)
```

| Module (`alternance/src/`) | Rôle |
|---|---|
| `commun.py` | réglages partagés (config, profil, contre-prompt, mode essai) |
| `donnees.py` | emplacement des données personnelles (`alternance/donnees/`), rangement automatique des anciens fichiers |
| `jours.py` | jours ouvrables, fériés, heure d'envoi des relances |
| `modele.py` | appels au modèle IA |
| `mails.py` | outils sur les adresses et le texte |
| `tableau.py` | tableau de suivi Excel (colonnes, statuts, doublons) |
| `messagerie.py` | choix de la messagerie (réglage `messagerie.type`) |
| `outlook.py` | Outlook classique : lecture, brouillons, boîte d'envoi |
| `imap.py` | Gmail / IMAP : lecture, brouillons déposés sur le serveur |
| `suivi.py` | mise à jour du suivi et relances |
| `sources.py` | liste « À contacter », alertes LinkedIn, La Bonne Alternance |
| `candidatures.py` | choix et rédaction des nouvelles candidatures |
| `sites.py` | site des entreprises : le trouver, y chercher une adresse ou un formulaire de contact |
| `reponses.py` | candidatures par formulaire : lettre et réponses aux questions |
| `refus.py` | liste des entreprises écartées par le filtre d'activité |

Les modules de l'interface (`web/src/`) sont décrits dans l'en-tête de `web/app.py`.

---

## 8. Ce qui n'est pas versionné

`config.json`, tout `alternance/donnees/` sauf les modèles `*.example.*` (config, profil, contre-prompt, tableau,
lettres et réponses, liste des refus), `linkedin/`, CV / PDF, `logs/`, `workspace/`, `corbeille/` — voir `.gitignore`.
