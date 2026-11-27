# Guide de démarrage

Ce guide t'accompagne de l'installation à ta première routine. Compte environ une heure, téléchargements compris.
Pour le détail de chaque réglage, voir le [README](README.md).

> **Rien n'est jamais envoyé à ta place.** LMAgent prépare des brouillons de mails et des lettres : tu relis et
> tu envoies toi-même.

---

## 1. Ce qu'il te faut avant de commencer

| Quoi | Pourquoi | Obligatoire ? |
|---|---|---|
| **Windows 10 ou 11** | LMAgent est une application Windows | oui |
| **LM Studio** et le modèle `qwen/qwen3.5-9b` | c'est l'IA qui écrit les lettres et les relances, sur ton PC (rien ne part sur Internet) | oui |
| Une **carte graphique** (NVIDIA, AMD, Intel Arc) | le modèle écrit beaucoup plus vite. Sans carte dédiée : le NPU des processeurs Intel Core Ultra, sinon le processeur (lent) | conseillé |
| Une **messagerie** : Outlook classique **ou** Gmail | les brouillons y sont déposés, les réponses y sont lues | oui |
| Un **jeton La Bonne Alternance** (gratuit) | pour trouver des entreprises qui recrutent en alternance autour de chez toi | conseillé |
| Ton **CV en PDF** (et ton calendrier d'alternance) | joints aux candidatures | oui |
| **Google Chrome** (ou Edge, Brave, Vivaldi, Opera) | pour préremplir les formulaires La Bonne Alternance | conseillé |
| Un **deuxième PC** avec carte graphique (« la tour ») | faire tourner l'IA ailleurs que sur ton PC portable | non (voir [docs/GUIDE_TOUR.md](docs/GUIDE_TOUR.md)) |

Excel n'est **pas** nécessaire : le tableau de suivi se consulte dans l'interface (page Suivi).

### Quelle messagerie choisir ?

- **Compte de l'école ou de l'entreprise (Microsoft 365)** : prends l'**Outlook classique** (celui de la suite
  Office, pas le « nouvel Outlook »). Ces comptes refusent l'accès par mot de passe des autres programmes.
- **Gmail** : rien à installer, il faut seulement créer un *mot de passe d'application* (étape 4).

---

## 2. Installer LMAgent et LM Studio

1. **LMAgent** : télécharge le dernier `LMAgent-X.Y.Z.msi` dans les *Releases* du dépôt GitHub et lance-le.
   L'installation se fait pour ton compte, sans droits administrateur. Windows peut afficher « éditeur inconnu » :
   l'installeur n'est pas signé, clique sur « Informations complémentaires » puis « Exécuter quand même ».
2. **LM Studio** : installe-le depuis [lmstudio.ai](https://lmstudio.ai), ouvre-le une fois, puis dans l'onglet
   de recherche des modèles télécharge **`qwen/qwen3.5-9b`**. Tu n'as rien d'autre à faire : LMAgent ouvre
   LM Studio, charge le modèle et le décharge tout seul à chaque routine.
   *(Avec la tour : LM Studio s'installe sur la tour, pas sur ton PC.)*

Les **mises à jour** de LMAgent s'installent ensuite toutes seules au démarrage.

---

## 3. Premier lancement : compte et assistant

1. Ouvre **LMAgent** (menu Démarrer ou bureau) : une icône apparaît près de l'horloge et l'interface s'ouvre
   dans ton navigateur (`http://127.0.0.1:8765`, accessible seulement depuis ton PC).
2. **Crée ton compte** : un identifiant et un mot de passe d'au moins 8 caractères. Ils protègent l'interface.
3. L'**assistant** pose quelques questions, une page par sujet :
   - **deuxième PC pour l'IA** : réponds non si tu n'as pas de tour ;
   - **messagerie** : Outlook ou Gmail (voir l'étape 4 pour Gmail) ;
   - **villes et jeton La Bonne Alternance** : les villes autour desquelles chercher des entreprises ;
   - **profil et signature** : qui tu es, ce que tu cherches ;
   - **CV** : ton fichier PDF, ajouté aux pièces jointes.

   Tu as déjà utilisé LMAgent sur un autre PC ? L'assistant peut **importer** ton ancienne installation.

Tout reste modifiable ensuite dans **Paramètres**, et l'assistant peut être relancé depuis cette page.

---

## 4. Brancher ta messagerie

### Avec l'Outlook classique

1. Ouvre l'Outlook classique et vérifie que ton compte y est configuré et synchronisé.
2. C'est tout : LMAgent l'ouvre en arrière-plan quand il en a besoin. Connecte-toi s'il le demande.
3. Si Outlook ajoute déjà ta signature aux nouveaux mails, laisse décochée la case « Ajouter ma signature »
   (Paramètres → Signatures), sinon elle apparaîtrait deux fois.

### Avec Gmail

1. Active la **validation en deux étapes** sur ton compte Google.
2. Crée un **mot de passe d'application** sur
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (nom : `LMAgent`)
   et copie les 16 lettres.
3. Dans **Paramètres → Messagerie** : messagerie `imap`, serveur `imap.gmail.com`, port `993`, ton adresse Gmail,
   et le mot de passe d'application. **Jamais ton vrai mot de passe Google.**
4. Gmail n'ajoute pas ta signature aux brouillons créés par un programme : coche « Ajouter ma signature »
   dans Paramètres → Signatures.

---

## 5. Les réglages à vérifier

Ouvre **Paramètres** : le menu à gauche range tout par catégorie, et le champ « Chercher un réglage » retrouve
n'importe quel réglage.

| Catégorie | Ce qu'il faut regarder |
|---|---|
| **👤 Mon profil** | **Profil** : formation, rythme et dates de l'alternance, postes visés, zone, projets à mettre en avant, style, et **un exemple de mail qui te plaît** (c'est ce qui donne le mieux ton ton au modèle). **Ce que je ne veux pas dans mes mails** : une interdiction par ligne (formules creuses, émojis, mots à bannir…) |
| **✍️ Signatures** | nom, titre, téléphone, mail, LinkedIn, portfolio, GitHub (un aperçu s'affiche à côté) ; « Première ligne de ta signature de mail » |
| **📨 Candidatures et relances** | nombre de candidatures par lancement, délai avant une relance ; **domaines de ton école** (ses mails ne sont jamais pris pour des réponses d'entreprise) ; **pièces jointes** : ton CV et ton calendrier d'alternance |
| **🔎 Recherche d'entreprises** | **jeton La Bonne Alternance** (compte gratuit sur api.apprentissage.beta.gouv.fr), **métiers** (codes ROME), **villes** et **rayon**, **activités acceptées** (codes NAF : par défaut l'informatique) |
| **🎓 Formulaire La Bonne Alternance** | ta situation, début et durée du contrat, école et formation, rythme, CV à joindre : ils servent à préremplir les formulaires |
| **📬 Messagerie** | voir l'étape 4 |
| **🖥️ Interface et compte** | thème clair / sombre, mot de passe, mises à jour |

Clique sur **Enregistrer** en bas de chaque catégorie. Les routines prennent les changements dès leur prochain
lancement.

---

## 6. L'extension Chrome (formulaires La Bonne Alternance)

Elle remplit pour toi le formulaire « Candidature simplifiée » de La Bonne Alternance (identité, lettre, réponses
aux questions, CV). Elle n'a accès ni à tes cookies ni à tes autres sites, et n'envoie jamais rien.

1. Page **À postuler** → bloc « 🧩 Extension Chrome LMAgent » → **Ouvrir la page des extensions**
   (le chemin du dossier est copié tout seul).
2. En haut à droite de cette page Chrome, active le **Mode développeur**.
3. Clique sur **Charger l'extension non empaquetée**, colle le chemin (Ctrl+V), puis **Sélectionner un dossier**.

Recharge la page À postuler : le bloc affiche « ✅ installée ». Chrome interdit qu'un programme installe une
extension tout seul, d'où ces trois clics, à faire une seule fois.

---

## 7. Facultatif : tes relations LinkedIn

Une recommandation interne augmente beaucoup les chances de réponse. Pour voir qui tu connais dans les entreprises
de ton tableau :

1. Sur LinkedIn : **Paramètres → Confidentialité des données → Obtenir une copie de vos données**, coche
   « Relations ».
2. LinkedIn t'envoie un lien par mail : télécharge l'archive `.zip`.
3. Page **LinkedIn** de LMAgent : dépose l'archive. Tu peux aussi ajouter une relation à la main.

---

## 8. Ta première routine

1. Page **Routines** : coche **essai** (rien n'est écrit, ni brouillon ni tableau), puis clique sur **🔎 Recherche**.
   L'avancement s'affiche en direct : passage, étape, entreprise en cours.
2. Si tout se passe bien, relance **sans** l'essai. Les brouillons arrivent dans ta messagerie, les candidatures par
   formulaire dans la page **À postuler**.
3. **Relis chaque brouillon** avant de l'envoyer. L'envoi est repéré tout seul au prochain passage, et la relance
   est prévue automatiquement.

| Routine | Ce qu'elle fait |
|---|---|
| 🔁 **Relances** | lit ta messagerie (réponses, envois) et écrit en brouillon les relances dues |
| 🔎 **Recherche** | trouve de nouvelles entreprises et écrit leurs candidatures |
| **Les deux** | relances puis recherche, à la suite |
| 📩 **Mails reçus** | met seulement le tableau à jour d'après ta messagerie |
| ✍️ **Réponses La Bonne Alternance** | écrit les lettres et réponses manquantes des formulaires |

### Tous les jours automatiquement

Page **Routines** → « ⏰ Tous les jours » : choisis une heure (et un nombre de passages) pour chaque routine.
Le Planificateur de tâches de Windows la lance chaque jour. Ton PC doit être allumé et ta session ouverte.

---

## 9. Au quotidien

- **Tableau de bord** : où tu en es (envois par semaine, réponses, entretiens, relances à faire).
- **À postuler** : candidatures prêtes à finaliser. Ouvre le formulaire prérempli ou envoie le brouillon, puis
  clique sur « ✅ Envoyée ».
- **Suivi** : toutes tes candidatures. La fiche ✏️ d'une entreprise se modifie (plusieurs adresses mail possibles,
  séparées par « ; »).
- **Écartées** : entreprises hors de ton domaine, à examiner (« Candidater quand même » ou « Abandonner »).
- **Rapport** : bilan d'une période, et un rapport rédigé par le modèle **pour toi** ou **pour ton école**,
  imprimable ou enregistrable en PDF.

---

## 10. En cas de souci

| Problème | Solution |
|---|---|
| « Le modèle ne répond pas » | vérifie que LM Studio est installé et que le modèle `qwen/qwen3.5-9b` est téléchargé |
| Outlook ne répond pas | ouvre l'Outlook classique, connecte-toi, attends la fin de la synchronisation, puis relance la routine |
| Gmail refuse la connexion | utilise un mot de passe d'application (étape 4), pas ton mot de passe Google |
| Le tableau ne s'enregistre pas | ferme le fichier s'il est ouvert dans Excel |
| Mot de passe de l'interface oublié | supprime `%APPDATA%\LMAgent\donnees\acces_interface.json` : la page de création du compte revient |
| Une page semble ancienne après une mise à jour | quitte LMAgent (⏻ ou l'icône près de l'horloge), relance-le, puis Ctrl+F5 |

Tes données (configuration, tableau, profil, journaux) sont dans **`%APPDATA%\LMAgent\`**. Les mises à jour et la
désinstallation n'y touchent jamais.
