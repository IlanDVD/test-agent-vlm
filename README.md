# Mon premier agent

Un projet pédagogique en français pour comprendre les agents IA : un assistant consulte les documents d'une boutique fictive, utilise leurs informations et répond à vos questions. Il fonctionne dans un terminal ou dans un chat web local.

Le code utilise **uniquement la bibliothèque standard de Python**. Aucun framework ni clé API n'est nécessaire. Le mode IA utilise un modèle installé dans Ollama ; une simulation permet aussi d'étudier la boucle sans modèle.

## Fonctionnalités

- Deux outils limités : lister les documents et lire un fichier texte.
- Boucle modèle → outils → observations → réponse.
- Chat local avec progression, actions consultables et questions de suivi.
- Conversations sauvegardées localement ; huit derniers échanges réussis transmis au modèle.
- Limites de génération et d'étapes, diagnostics et tests automatisés.

## Prérequis

- Python **3.10 ou plus**.
- Pour le mode IA : [Ollama](https://ollama.com/download) en cours d'exécution et un modèle compatible avec les appels d'outils.

Téléchargez le modèle utilisé dans l'exemple :

```sh
ollama pull qwen3:4b
```

Le téléchargement du modèle est distinct du code de ce dépôt. Sa vitesse dépend de votre matériel.

## Démarrer le chat

Sous Windows, double-cliquez sur `LANCER-CHAT.cmd`, ou depuis PowerShell :

```powershell
.\LANCER-CHAT.cmd
```

Le lanceur cherche Python automatiquement, puis ouvre [http://127.0.0.1:8765](http://127.0.0.1:8765). Gardez sa fenêtre ouverte pendant l'utilisation.

Avec Python installé, sous Windows, macOS ou Linux :

```sh
python chat_local.py --ouvrir
```

Selon votre installation, remplacez `python` par `python3` ou `py -3`. L'option `-3` appartient au lanceur `py`, pas à `python`.

Essayez « Quel est le prix du carnet bleu ? », puis « Et pour deux exemplaires ? ». Les données de la boutique sont fictives. Les frais présents dans `documents/livraison.txt` font partie de l'exercice et peuvent être modifiés.

## Utiliser le terminal

Simulation sans IA, avec choix prédéfinis et lectures réelles :

```sh
python agent.py --pas-a-pas
```

Vrai modèle local :

```sh
python agent.py --mode ollama --model qwen3:4b --question "Quel est le délai de livraison ?"
```

Sous Windows, `agent.cmd` permet aussi de lancer le programme en trouvant Python automatiquement :

```powershell
.\agent.cmd --mode ollama --model qwen3:4b --question "Quel est le délai de livraison ?"
```

## Fonctionnement

```text
Navigateur ou terminal
        ↓
Programme Python : contexte, boucle et permissions
        ↔ Ollama : choix des outils et réponse
        ↔ documents/*.txt : données consultables
```

Le modèle propose des appels d'outils ; Python valide leurs paramètres et exécute les lectures. Le chat ajoute la gestion de conversations autour de la même boucle.

## Tests

```sh
python -m unittest -v tests tests_chat
```

Les tests automatisés n'appellent pas de modèle réel. Ils vérifient notamment les limites d'accès aux fichiers, les erreurs, la lecture de plusieurs documents, le contexte, la persistance et les routes du serveur.

## Structure

| Fichier ou dossier | Rôle |
|---|---|
| `agent.py` | Moteur, outils et adaptateur Ollama |
| `chat_local.py` | Serveur local et conversations |
| `web/` | Interface du chat |
| `documents/` | Données fictives |
| `tests.py`, `tests_chat.py` | Tests sans modèle réel |
| `GUIDE.md` | Explications et exercices sur les agents |
| `CHAT-LOCAL.md` | Lancement et fonctionnement du chat |

`conversations/` et `journaux/` sont créés à l'exécution et exclus de Git, ainsi que les environnements Python et fichiers `.env`. Les deux fichiers `exemple-*.json` sont des traces pédagogiques conservées avec le projet.

## Limites de l'exemple

Le serveur écoute uniquement sur `127.0.0.1` et n'est pas destiné à être exposé sur Internet. Un seul message est traité à la fois. Une génération peut durer plusieurs minutes. Les réponses doivent être vérifiées : un agent peut mal interpréter les documents ou faire une erreur de calcul.

Le contexte du chat n'est pas un entraînement du modèle. Le fil est conservé après actualisation dans le même onglet ; cette version ne propose pas de catalogue des anciennes conversations.

Pour aller plus loin, consultez le [guide pédagogique](GUIDE.md) et le [guide du chat](CHAT-LOCAL.md).
