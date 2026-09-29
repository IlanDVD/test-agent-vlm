# Lire une image avec l’agent

Le modèle qwen3:4b choisit les outils. L’outil analyser_image transmet une image
à qwen2.5vl:3b, puis renvoie son interprétation à l’agent. Le modèle visuel ne
dispose pas lui-même des outils de l’agent.

## Démarrer

Installer le modèle si nécessaire (environ 3,2 Go) :

```powershell
ollama pull qwen2.5vl:3b
.\LANCER-CHAT.cmd --vision-model qwen2.5vl:3b
```

Si un ancien serveur tourne encore, arrêter sa console avec Ctrl+C avant de
relancer. Sinon, utiliser `--port 8766` pour ouvrir une instance distincte.
Actualiser la page ne recharge pas le code Python du serveur.

Dans le chat, demander :

> Analyse facture-demo-2026-001.png. Quels articles, quantités, frais de livraison et total vois-tu ?

Puis :

> Consulte aussi retours.txt et indique les conditions de retour.

Les détails des actions montrent l’observation du VLM, distincte de la synthèse
finale. Le nom du modèle visuel apparaît dans le chat. Les fichiers sont listés
au chargement de la page : actualiser après avoir ajouté une image.

En terminal :

```powershell
.\agent.cmd --mode ollama --model qwen3:4b --vision-model qwen2.5vl:3b --question "Analyse facture-demo-2026-001.png et donne son total."
```

## Comprendre le code

- skills.py déclare l’outil, valide ses paramètres et liste les fichiers.
- vision.py vérifie le chemin, la taille (10 Mo maximum) et la signature PNG/JPEG,
  encode les octets en base64 et appelle l’API locale Ollama. Le décodage complet
  de l’image est effectué par Ollama ; une signature valide ne garantit pas un fichier valide.
- agent.py transmet le modèle visuel à l’outil et poursuit la boucle avec son résultat.
- chat_local.py configure les deux modèles ; web/app.js affiche les étapes et observations.

Les images ne sont pas incorporées dans les journaux. Les analyses textuelles
le sont. L’historique des échanges contient les réponses finales, pas les images :
l’agent doit réutiliser l’outil pour vérifier un détail visuel.

L’analyse peut durer plusieurs minutes. Deux modèles demandent davantage de
mémoire ; le modèle visuel est déchargé après chaque appel. Une image illisible,
une réponse tronquée ou un modèle absent produit une erreur d’outil explicite.
Les chiffres reconnus restent à vérifier. Aucun calculateur déterministe n’est
ajouté dans cette version. Les PDF ne sont pas acceptés : exporter d’abord les
pages souhaitées en PNG/JPEG. Aucun téléversement depuis le navigateur : déposer
les images dans documents.

## Vérifier

```powershell
python -m unittest -v tests tests_chat tests_vision
```

Résultat attendu pour la facture fournie : 4 stylos à 3 EUR, 1 carnet à 12 EUR,
sous-total 24 EUR, livraison 49,90 EUR, total 73,90 EUR. Comparer manuellement
ces données à l’analyse ; un test simulé valide le programme, pas la justesse du VLM.

Documentation : https://docs.ollama.com/capabilities/vision
