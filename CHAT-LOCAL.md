# Discuter avec votre agent dans le navigateur

## Démarrer

1. Ouvrez Ollama si l'application n'est pas déjà active. Le modèle `qwen3:4b` doit être installé, comme pour la version terminal.
2. Double-cliquez sur **LANCER-CHAT.cmd** dans ce dossier. Il trouve le Python déjà disponible et ouvre le navigateur automatiquement.
3. Écrivez votre question et cliquez sur **Envoyer**, ou appuyez sur Entrée. Maj + Entrée insère une nouvelle ligne.

Depuis PowerShell, vous pouvez aussi lancer :

```powershell
.\LANCER-CHAT.cmd
```

L'adresse habituelle est [http://127.0.0.1:8765](http://127.0.0.1:8765). Gardez la fenêtre du lanceur ouverte pendant l'utilisation. Pour arrêter le serveur lancé dans cette fenêtre, appuyez sur Ctrl+C. Si le serveur est déjà actif à cette adresse, le lanceur ouvre simplement le chat existant.

Aucune bibliothèque Python supplémentaire, clé API ou connexion Telegram n'est nécessaire. L'interface n'est pas publiée sur Internet. Le serveur écoute uniquement sur votre ordinateur ; le dessin adapté aux petits écrans ne rend pas le chat accessible depuis votre téléphone.

## Essayer une vraie conversation

Envoyez d'abord :

> Quel est le prix du carnet bleu ?

Puis :

> Et pour deux exemplaires ?

La seconde question reprend le contexte de la première. Vous pouvez aussi demander un panier livraison comprise : l'agent dispose des mêmes outils de lecture qu'auparavant, avec le budget corrigé de 8 192 tokens.

Pendant l'attente, l'interface affiche l'étape en cours et le temps écoulé. Qwen3 peut prendre une ou plusieurs minutes, selon votre matériel et la question. La réponse finale apparaît lorsqu'elle est complète ; elle n'est pas affichée mot par mot.

Sous chaque réponse, dépliez les **actions consultables** pour voir les documents lus et le nombre de tokens générés. Les étapes visibles sont des appels d'outils et des informations de progression, pas les pensées internes du modèle.

## Mémoire et nouvelle conversation

- L'historique visible est conservé si vous actualisez la page dans le même onglet.
- Les **8 derniers échanges réussis** sont transmis au modèle avec votre nouvelle question. Les messages plus anciens restent visibles mais ne font plus partie du contexte envoyé.
- Les conversations sont sauvegardées dans `conversations/`, au format JSON, sur votre ordinateur. Elles contiennent vos questions, les réponses et les observations des outils.
- Le bouton **Nouvelle conversation** ouvre un fil vide et sans contexte antérieur. Les anciens fichiers restent sur le disque. Cette version n'a pas encore de liste permettant de rouvrir un ancien fil après fermeture de l'onglet.
- Un seul message est traité à la fois. Les boutons se réactivent à la fin de la réponse.
- Si le serveur est arrêté pendant un traitement, cette réponse est marquée comme interrompue au prochain chargement. Vous pouvez renvoyer votre question ; le programme ne déclare pas le traitement réussi.

Le contexte conversationnel ne réentraîne pas le modèle : nous lui redonnons les messages pertinents à chaque appel.

## Les étapes de la construction

### 1. Réutiliser le moteur de l'agent

`agent.py` conserve la boucle existante : modèle → demande d'outil → lecture → observation → modèle. La fonction `lancer` accepte maintenant un historique et un rappel qui signale les événements. Les commandes terminal précédentes restent valables.

### 2. Ajouter un serveur local

`chat_local.py` reçoit les questions du navigateur, lance l'agent en arrière-plan, sauvegarde les échanges et expose la progression. Il garde le navigateur réactif pendant une génération lente. Les fichiers sont sauvegardés par remplacement atomique pour éviter un fichier JSON partiellement écrit.

Le serveur utilise uniquement la bibliothèque standard de Python. Il sert une liste limitée de fichiers de l'interface, vérifie l'origine des requêtes et demande un jeton local pour envoyer un message. C'est une application personnelle locale, pas un serveur destiné à être exposé publiquement.

### 3. Construire le chat

Le dossier `web/` contient la page, sa mise en forme et les interactions. Le navigateur demande périodiquement l'avancement au serveur, puis affiche le résultat et les sources. Les textes du modèle ne sont jamais exécutés comme du HTML ; seuls les passages en gras sont mis en forme simplement.

Le trajet d'un message est :

**Navigateur → serveur Python → Ollama → outils de lecture → réponse dans le navigateur.**

Ollama produit la réponse ; le serveur gère la conversation ; le navigateur fournit l'interface.

## En cas de problème

**Ollama indisponible :** ouvrez Ollama puis actualisez le chat. L'interface vérifie sa disponibilité au chargement. Si le modèle manque, exécutez `ollama pull qwen3:4b` dans PowerShell.

**Connexion perdue :** relancez `LANCER-CHAT.cmd` puis actualisez la page. Dans le même onglet, la conversation sauvegardée peut être retrouvée.

**Port déjà utilisé par une autre application :** lancez `LANCER-CHAT.cmd --port 8766` ; le navigateur ouvrira l'autre adresse locale. Le stockage du navigateur dépend de l'adresse, donc il s'agit d'un onglet de conversation distinct.

**Changer de modèle installé :** lancez par exemple `LANCER-CHAT.cmd --model NOM_DU_MODELE`. Arrêtez d'abord le serveur existant, sinon le lanceur réouvrira celui qui fonctionne déjà avec son ancienne configuration. Le modèle doit prendre en charge les outils.

**Limite de tokens atteinte :** l'interface affiche l'erreur de l'agent. La version terminal permet de régler `--max-tokens` ; cette première interface utilise le défaut de 8 192 tokens. Le chat ne relance pas automatiquement un traitement échoué.

## Fichiers utiles

| Fichier | Rôle |
|---|---|
| `LANCER-CHAT.cmd` | Démarrage et ouverture du navigateur |
| `chat_local.py` | Serveur et conversations |
| `web/index.html` | Structure du chat |
| `web/style.css` | Présentation ordinateur et mobile |
| `web/app.js` | Envoi, progression, historique et nouveau fil |
| `agent.py` | Outils et boucle de l'agent |
| `conversations/` | Vos conversations sauvegardées |

Les tests se relancent avec `python -m unittest -v tests tests_chat`, en utilisant le Python disponible sur votre ordinateur.

## Vérifications effectuées

Les 21 tests automatisés du moteur et du chat ont réussi. Le navigateur a été vérifié sur ordinateur et à 390 pixels de largeur, sans débordement horizontal. Un échange réel avec Ollama et une question de suivi ont été exécutés ; l'actualisation conserve le fil et « Nouvelle conversation » le réinitialise. Aucun problème JavaScript n'a été relevé pendant ce parcours.

Le modèle peut malgré tout mal répondre : lors d'un essai, il reconnaissait le carnet de la question précédente mais refusait de calculer deux exemplaires sans tarif de lot. Les instructions ont été précisées pour autoriser quantité × prix unitaire, sans inventer de réduction. Vérifier la justesse des réponses reste distinct de vérifier que le chat fonctionne.

Après cette précision, un nouveau test réel du moteur avec l'historique de la première question a répondu : « Le prix pour deux exemplaires de carnet bleu est de 24 EUR (12 EUR × 2). »
