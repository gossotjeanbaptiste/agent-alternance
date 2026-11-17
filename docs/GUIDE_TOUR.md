# Réglage de la tour : réveil à distance, veille et arrêt

But : les scripts du ThinkPad **réveillent la tour** (Wake-on-LAN), utilisent son modèle,
puis la laissent allumée (remise en veille possible avec `veille_apres`). `python src\tour` permet aussi de l'éteindre à distance.

Tout se fait **sur la tour**, une seule fois. Compte 15 minutes.

---

## 1. Wake-on-LAN (pour la réveiller)

### a) Vérifier que la tour est en Ethernet
Le Wake-on-LAN marche mal (ou pas) en Wi-Fi. Dans PowerShell sur la tour :
```powershell
Get-NetAdapter | Format-Table Name, InterfaceDescription, MacAddress, Status
```
La carte **Ethernet** doit avoir l'adresse `(adresse MAC de la tour, celle de config.json)` (celle que le ThinkPad voit).
Si c'est la carte Wi-Fi qui a cette adresse, branche la tour en câble et donne-moi l'adresse de la carte Ethernet.

### b) Dans le BIOS
Redémarre la tour, entre dans le BIOS (souvent `Suppr` ou `F2`) et active l'option du genre :
- **Wake on LAN**, **Resume by PCI-E / PCIe device**, ou **Power On by PCI-E**
- désactive **ErP / EuP Ready** s'il existe (sinon la carte réseau est coupée quand le PC dort)

### c) Dans Windows (carte réseau)
Gestionnaire de périphériques → **Cartes réseau** → ta carte **Ethernet** → Propriétés :
- onglet **Gestion de l'alimentation** : coche **« Autoriser ce périphérique à sortir l'ordinateur du mode veille »**
  et **« Autoriser uniquement un paquet magique à sortir l'ordinateur du mode veille »**
- onglet **Avancé** : **Wake on Magic Packet** → **Activé** (et *Wake on pattern match* peut rester désactivé)

### d) Désactiver le démarrage rapide (pour le réveil depuis l'arrêt complet)
Panneau de configuration → Options d'alimentation → **Choisir l'action des boutons d'alimentation**
→ *Modifier des paramètres actuellement non disponibles* → décoche **Activer le démarrage rapide**.

> ⚠️ **Préfère la veille à l'arrêt.** En veille, LM Studio reste ouvert avec son serveur démarré :
> la tour est prête en quelques secondes. Après un arrêt complet, Windows attend que tu ouvres ta session
> et LM Studio ne tourne pas : les scripts basculeront alors sur le ThinkPad.

---

## 2. SSH (pour la mettre en veille / l'éteindre à distance)

Dans **PowerShell en administrateur** sur la tour :

### a) Installer et démarrer le serveur SSH
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

### b) N'autoriser que le ThinkPad (via Tailscale) et ton réseau local
Le réseau local sert de secours : si Tailscale est coupé sur la tour, le script passe par là pour le relancer.
```powershell
Set-NetFirewallRule -Name OpenSSH-Server-In-TCP -RemoteAddress <IP Tailscale du portable, ex. 100.x.y.z>,LocalSubnet
```
Comme SSH devient joignable depuis ton réseau local, **interdis la connexion par mot de passe**
(seule la clé du ThinkPad marchera) :
```powershell
$f = "C:\ProgramData\ssh\sshd_config"
Set-Content $f (@("PasswordAuthentication no") + (Get-Content $f))
Restart-Service sshd
```
(La ligne est ajoutée **en haut** du fichier exprès : à la fin, elle ne s'appliquerait qu'au bloc `Match` qui s'y trouve.)

Puis, dans `config.json` du ThinkPad, rubrique `tour` : `"ssh_lan": "utilisateur@192.168.1.XX"`
(adresse locale de la tour — réserve-la dans ta box pour qu'elle ne change pas).

### c) Installer la clé du ThinkPad (connexion sans mot de passe)
Si ton compte Windows sur la tour est **administrateur** (cas le plus courant) :
```powershell
Add-Content -Path C:\ProgramData\ssh\administrators_authorized_keys -Value "<contenu de ~/.ssh/id_ed25519.pub du portable>"
icacls.exe C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "*S-1-5-32-544:F" /grant "*S-1-5-18:F"
```
(La deuxième commande restreint les droits du fichier : sans ça, SSH ignore la clé.)

Si ton compte **n'est pas administrateur**, mets plutôt la même ligne dans `C:\Users\utilisateur\.ssh\authorized_keys`.

---

## 2 bis. Tailscale sans icône (optionnel)

Tailscale peut tourner sans son icône près de l'horloge : c'est le service Windows qui garde la connexion.
1. Mode « sans surveillance » : `tailscale set --unattended=true` (sur chaque PC).
2. **Paramètres → Applications → Démarrage** → désactive **Tailscale** (sinon l'icône revient au prochain démarrage).
3. Quitte l'icône. Pour la retrouver : menu Démarrer → Tailscale.

## LM Studio n'a pas besoin de rester ouvert

Si LM Studio est fermé sur la tour, le script l'ouvre dans ta session Windows (même verrouillée) via une tâche
planifiée `lm_agent_lmstudio` (créée automatiquement la première fois), puis le referme à la fin.
Il faut seulement que ta session soit ouverte (tour en veille ou verrouillée : OK ; après un redémarrage : non).

## 3. Tester depuis le ThinkPad

```bash
python src\tour etat
```
Les deux lignes doivent être ✅. Puis :
```bash
python src\tour veille
```
La tour doit s'endormir. Attends 30 secondes, puis :
```bash
python src\tour reveiller
```
Elle doit se rallumer et LM Studio répondre (« Tour réveillée et LM Studio prêt en X s »).

---

## Comment ça marche ensuite

- Quand tu lances `relances.py`, `recherche.py` ou `alternance.py` :
  1. ce qui est éteint est rallumé : Tailscale du ThinkPad, la tour si elle dort (**Wake-on-LAN**),
     Tailscale de la tour (par le réseau local), le **serveur LM Studio** de la tour (par SSH) ;
  2. chargement du modèle, travail ;
  3. déchargement du modèle ;
  4. remise en veille **seulement si `"veille_apres": true`** dans `config.json` (désactivé par défaut),
     et seulement si la tour dormait vraiment : si elle est allumée, le script n'y touche jamais.
- Si la tour ne se réveille pas (hors de chez toi, Wake-on-LAN pas réglé…), le script bascule
  sur le modèle du ThinkPad, plus lent mais la routine ne saute pas.
- Pour que la tour se rendorme après le travail : `"veille_apres": true` dans `config.json` (rubrique `tour`).

## Si tu joues sur la tour

Avant d'utiliser la tour, le script lit l'état de sa carte graphique (`nvidia-smi`, simple lecture par SSH).
Si un jeu l'occupe (moins de 7000 Mo libres, ou plus de 40 % d'utilisation), il **n'y touche pas** : ni LM Studio,
ni chargement du modèle. Le travail se fait sur le ThinkPad, plus lentement, mais ton jeu n'est pas dérangé.
Réglages dans `config.json`, rubrique `tour` : `verifier_gpu`, `vram_libre_min_mo`, `gpu_utilisation_max`.

## Commandes de la tour (`python src\tour`)

| Commande | Effet |
|---|---|
| `python src\tour etat` | allumée ? LM Studio ? SSH ? |
| `python src\tour reveiller` | rallume ce qui est éteint (tour, Tailscale, serveur LM Studio) |
| `python src\tour serveur` | démarre le serveur LM Studio de la tour |
| `python src\tour tailscale` | relance Tailscale sur le ThinkPad et sur la tour |
| `python src\tour veille` | mise en veille |
| `python src\tour eteindre` | arrêt dans 60 s (`--maintenant` pour tout de suite) |
| `python src\tour redemarrer` | redémarrage dans 60 s |
| `python src\tour annuler` | annule un arrêt / redémarrage en cours |

Ajoute `--oui` pour sauter la confirmation.

## Limites

- **Réveil depuis l'extérieur** : le paquet de réveil est aussi envoyé à ta box par Internet
  (adresse publique de ta box, ports UDP 7 et 9, rubrique `wol_internet` de `config.json`), et la box le relaie vers la tour.
  Pour que ça tienne dans le temps :
  - dans la box, **réserve l'adresse 192.168.1.XX pour la tour** (bail DHCP statique / « IP fixe »),
    sinon la tour peut changer d'adresse et le réveil viser la mauvaise ;
  - si le port configuré dans la box n'est pas 9, mets le bon dans `"ports"` ;
  - si ton adresse publique change un jour (rare chez la plupart des opérateurs français, mais possible),
    mets la nouvelle dans `"hote"` — ou un nom DynDNS si ta box en propose un.
- La veille / l'arrêt via SSH marchent de partout grâce à Tailscale.
