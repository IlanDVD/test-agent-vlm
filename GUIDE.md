# Mon premier agent : apprendre en observant

**Nouveau : un chat dans votre navigateur.** Double-cliquez sur `LANCER-CHAT.cmd` pour discuter avec l'agent et poser des questions de suivi. Le guide [CHAT-LOCAL.md](CHAT-LOCAL.md) explique le lancement, la mémoire, les étapes visibles et le fonctionnement de cette interface.

Ce projet contient un petit assistant documentaire en Python. Il répond à des questions sur une boutique **entièrement fictive**, en consultant trois fichiers. Il ne passe aucune commande et ne modifie pas les documents.

Deux modes partagent les mêmes outils et la même boucle :

- **Démonstration** : les décisions sont programmées à l'avance. Aucun modèle, compte ou accès Internet. Les lectures de fichiers sont réelles. C'est une simulation de la mécanique d'un agent, pas une IA autonome.
- **Ollama** : un vrai modèle choisit les outils et rédige la réponse. Ce mode nécessite Ollama et un modèle local compatible avec les appels d'outils. Le modèle n'est pas fourni dans ce dossier.

## 1. Votre première expérience

Sur cet ordinateur, ouvrez `LANCER-DEMO.cmd` dans l'Explorateur Windows. Appuyez sur Entrée pour avancer à chaque appel d'outil. Le lanceur utilise Python s'il est disponible, notamment la version embarquée avec cet environnement.

Dans un terminal, depuis ce dossier, l'équivalent est :

```powershell
.\agent.cmd --pas-a-pas
```

Le lanceur `agent.cmd` trouve automatiquement Python, y compris la version déjà disponible sur cet ordinateur. Aucune installation supplémentaire n'est nécessaire ici. Sur un autre ordinateur, il faut Python 3.10 ou plus. L'option `-3` appartient à `py` : écrire `py -3 agent.py`, jamais `python -3 agent.py`. Aucune commande `pip install` n'est nécessaire.

La question prédéfinie est : « Quels sont le délai et les frais de livraison en France métropolitaine ? »

Vous verrez :

1. La simulation demande `lister_documents`.
2. Python renvoie les noms des trois fichiers.
3. La simulation demande `lire_document` avec le nom `livraison.txt`.
4. Python renvoie le contenu réel du document.
5. La simulation restitue ce contenu avec sa source et termine.

Le résultat mentionne **3 à 5 jours ouvrés après expédition**, **4,90 EUR**, la gratuité à partir de **50 EUR**, et le délai de préparation inconnu. En mode démonstration, ce texte est extrait du fichier, sans synthèse par une IA.

Un journal de chaque exécution est créé dans `journaux/`. Il contient la question, les appels, les paramètres, les observations et la réponse finale. Il ne représente pas les pensées internes d'un modèle.

## 2. Ce que vous avez vraiment construit

Un modèle produit des réponses et peut proposer des appels d'outils. Votre programme lui donne les moyens d'agir et lui renvoie les résultats.

**Objectif → modèle → demande d'outil → contrôle par Python → exécution → observation → modèle → réponse ou nouvelle action.**

| Élément | Son rôle | Où le voir dans le code |
|---|---|---|
| Objectif | Ce que demande l'utilisateur | `QUESTION`, puis `--question` |
| Instructions | Mission, limites, format de réponse | `MISSION` |
| Modèle | Choisit une action ou répond | `modele_ollama` |
| Schémas d'outils | Décrivent les fonctions et leurs paramètres | `OUTILS` |
| Exécution | Vérifie puis effectue l'action demandée | `executer_outil` |
| Contexte | Garde la question, les appels et les observations | `messages` dans `lancer` |
| Boucle | Répète jusqu'à une réponse ou une limite | `lancer` |
| Traces | Permettent de comprendre et tester le comportement | `trace`, dossier `journaux` |

**Le modèle ne lit pas directement votre disque.** Il demande par exemple une fonction et un nom de fichier. C'est le code Python qui décide si la lecture est autorisée, puis l'effectue.

Un chatbot sans outils produit du texte. Un workflow suit un chemin décidé par son développeur. Dans le mode IA de cet exemple, le modèle peut choisir le document utile, en consulter plusieurs ou constater qu'il manque une information : une partie du chemin dépend de lui.

## 3. Lire le code dans le bon ordre

Commencez par `OUTILS` : c'est le menu proposé au modèle. Lisez ensuite `executer_outil` pour voir les actions réellement permises. Puis regardez `lancer`, le cœur du système :

```python
reponse = decider(messages)
messages.append(reponse)
# S'il y a une demande d'outil :
resultat = executer_outil(nom, arguments, dossier)
messages.append({"role": "tool", "tool_name": nom,
                 "content": json.dumps(resultat)})
# Le tour suivant redonne tout cet historique au modèle.
```

Cet extrait illustre la boucle ; le fichier complet contient les vérifications et les conditions d'arrêt.

Enfin, comparez `modele_simule` et `modele_ollama`. La première est un scénario écrit à la main. La seconde appelle un modèle. Tout le reste est commun : c'est ainsi qu'on sépare le modèle du programme qui l'entoure.

## 4. Faire trois expériences sans IA

**Expérience A — modifier une observation.** Changez le délai dans `documents/livraison.txt`, puis relancez. La réponse reflète votre modification sans changement du programme. Vous voyez pourquoi donner des données à un agent est différent de réentraîner son modèle.

**Expérience B — rencontrer une erreur.** Lancez :

```powershell
.\agent.cmd --demo-erreur --pas-a-pas
```

La simulation demande volontairement un fichier inexistant, reçoit une erreur, puis demande le bon fichier. La récupération est elle aussi programmée dans la simulation ; un vrai modèle devrait choisir lui-même la suite.

**Expérience C — limiter l'autonomie.** Lancez :

```powershell
.\agent.cmd --max-tours 1
```

Le programme s'arrête après son premier tour, sans déclarer la tâche réussie. Un tour correspond à un appel au décideur ; il peut comporter jusqu'à cinq demandes d'outils.

La simulation refuse une question différente : elle n'a pas de compréhension générale du langage.

## 5. Passer à une vraie IA

L'adaptateur fourni utilise [Ollama](https://docs.ollama.com/), qui permet notamment d'exécuter des modèles localement. C'est un choix pour cet exemple, pas une obligation architecturale.

1. Installez Ollama si vous souhaitez essayer ce mode.
2. Choisissez et téléchargez un modèle **local compatible avec les outils**, adapté à la mémoire de votre ordinateur. [qwen3:4b](https://ollama.com/library/qwen3:4b) est un exemple de taille modeste de la famille Qwen3 ; vérifiez les ressources nécessaires avant téléchargement. Les performances restent dépendantes du matériel et du modèle.
3. Assurez-vous que le service Ollama est démarré.
4. Dans le terminal, lancez, avec le nom exact du modèle installé :

```powershell
ollama pull qwen3:4b
.\agent.cmd --mode ollama --model qwen3:4b --pas-a-pas
```

Le téléchargement peut représenter plusieurs gigaoctets. Le script n'installe et ne télécharge rien automatiquement. Le mode avec un modèle local ne nécessite pas de clé d'API de fournisseur ; il utilise les ressources de votre ordinateur. Évitez un modèle distant/cloud si vous souhaitez que les documents restent traités localement.

Essayez ensuite :

```powershell
.\agent.cmd --mode ollama --model qwen3:4b --question "Puis-je retourner un carnet ? Cite tes sources et précise ce qui manque."
.\agent.cmd --mode ollama --model qwen3:4b --question "Le carnet bleu est-il disponible en stock ?"
```

Pour la seconde question, la bonne réponse reconnaît l'absence de données de stock. Une réponse assurée serait une erreur, même si le programme s'est exécuté sans problème.

Si la connexion échoue, vérifiez qu'Ollama fonctionne sur `127.0.0.1:11434`. Si le modèle n'existe pas, vérifiez son nom avec `ollama list`. Si les outils sont refusés, choisissez un modèle compatible. Un délai de 300 secondes maximum s'applique à chaque requête ; un modèle trop lent peut le dépasser.

L'interface utilisée est documentée dans [l'API chat](https://docs.ollama.com/api/chat) et [les appels d'outils](https://docs.ollama.com/capabilities/tool-calling). Pour changer de fournisseur, remplacez l'adaptateur et adaptez ses messages ; les formats ne sont pas nécessairement identiques.

## 6. Les notions à connaître ensuite

**Contexte et mémoire.** Ici, `messages` est une mémoire de travail pour une seule exécution. Le journal est sauvegardé, mais il n'est pas relu au démarrage : il n'y a donc pas de mémoire persistante active. Celle-ci demanderait de sélectionner puis de réintroduire des informations utiles dans une prochaine exécution.

**Recherche documentaire, ou RAG.** Cet exemple récupère des documents avant de répondre. Pour des milliers de documents, on remplacerait la liste complète par une recherche de passages pertinents, éventuellement avec un index sémantique. Une base vectorielle n'est pas indispensable pour trois fichiers.

**Instructions et permissions.** Une consigne explique au modèle ce qu'il doit faire. Une vérification dans le code limite ce qu'il peut effectivement faire. Ici, seuls deux outils et des fichiers texte du dossier prévu sont permis ; aucun terminal n'est exposé au modèle. Ce contrôle constitue une limite de l'exemple, pas un bac à sable complet contre un autre processus malveillant.

**Instructions malveillantes dans les documents.** Un document pourrait contenir « ignore ta mission ». La consigne demande de traiter cela comme une donnée. Cette consigne ne garantit pas que le modèle résistera ; les limites imposées par le programme réduisent les actions possibles. L'agent peut toujours produire une mauvaise réponse.

**Coûts et latence.** Chaque tour peut envoyer un historique plus long au modèle. Avec une API payante, cela peut augmenter la facture ; en local, cela consomme du temps et de la mémoire. Une limite de tours est utile mais ne constitue pas à elle seule un plafond monétaire.

**Arrêt et réussite.** L'absence d'appel d'outil met fin à la boucle. Elle ne prouve pas que la réponse est correcte. Dans un agent de programmation, des tests et une revue des changements serviraient de vérifications supplémentaires.

**Autonomie et validation humaine.** Ici, les outils lisent seulement des documents. Pour envoyer un message, payer ou modifier des données, ajoutez des autorisations adaptées et une validation avant les actions sensibles. L'option pas à pas sert à apprendre ; elle ne constitue pas un système complet d'approbation.

**Plusieurs agents.** Un agent suffit pour commencer. Plusieurs agents peuvent répartir un travail complexe, mais demandent de gérer coordination, coût, conflits et vérification. Leur nombre n'est pas une mesure de qualité.

**Frameworks et MCP.** Un framework peut fournir la boucle, les traces et la gestion d'état. MCP peut standardiser la connexion à des outils. Vous n'avez besoin ni de l'un ni de l'autre pour comprendre et faire fonctionner cet exemple.

## 7. Mesurer l'utilité

Un agent est utile quand il faut choisir des actions en fonction d'informations découvertes pendant le travail : consulter plusieurs sources, enquêter sur un problème, examiner du code et réagir aux tests. Pour une tâche toujours identique, un script déterministe est souvent plus simple à vérifier.

Testez le mode IA sur ces cas :

| Question ou situation | Résultat attendu |
|---|---|
| Délai de livraison | 3 à 5 jours ouvrés après expédition ; estimation |
| Frais de livraison | 4,90 EUR, offerts à partir de 50 EUR |
| Stock du carnet | Information indisponible |
| Frais de retour | Information indisponible |
| Document absent | Absence reconnue, pas de fait inventé |
| Chemin vers un fichier extérieur | Refus par le programme |

Vérifiez la qualité de la réponse, les sources, le nombre d'actions et les échecs. Répétez quelques questions : un modèle peut varier d'une exécution à l'autre. Les tests de `tests.py` vérifient la mécanique, pas l'intelligence ou la fidélité d'un modèle réel.

## 8. Prolonger l'exemple

1. Ajoutez un quatrième document et posez une question qui nécessite deux sources en mode IA.
2. Ajoutez un outil `rechercher_documents(mot)` pour éviter de tout lire.
3. Ajoutez un calculateur à paramètres limités, sans exécution arbitraire de code.
4. Mesurez les résultats sur dix questions dont vous connaissez les réponses.
5. Ensuite seulement, envisagez un agent qui modifie du code dans un dossier isolé et lance une commande de tests contrôlée.

Ce projet couvre les bases par un exemple complet, maintenant utilisable dans le terminal ou dans le chat web local. Il reste volontairement petit : pas de tâches planifiées, d'accès à vos comptes ni de déploiement en production.

Référence générale : [Building effective agents, Anthropic](https://www.anthropic.com/engineering/building-effective-agents).

## Vérification de cette livraison

Les quinze tests automatisés ont réussi. Ils couvrent notamment deux lectures successives, deux lectures dans le même tour, les réponses tronquées, les réponses contenant uniquement de la réflexion et le budget personnalisable. `exemple-journal.json` conserve la trace de la démonstration initiale.

Un test réel avec `qwen3:4b` a également réussi après correction : liste des documents, lecture de `produits.txt`, lecture de `livraison.txt`, puis réponse citant les deux sources. Avec les fichiers présents au moment du test (livraison modifiée à 49,90 EUR), le modèle a répondu 24,00 EUR d'articles + 49,90 EUR de livraison = 73,90 EUR. La trace figure dans `exemple-panier-ollama.json`. Cela confirme cette exécution, sans garantir toutes les réponses futures du modèle.

Pour relancer les tests depuis ce dossier : `python -m unittest -v tests`.

## Pourquoi Qwen3 pouvait s'arrêter avant de lire les documents

L'ancienne version demandait au maximum 2 048 tokens de génération sans préciser le mode de réflexion. Sur la question du panier avec livraison, une reproduction réelle a renvoyé `done_reason: "length"`, `eval_count: 2048`, du contenu dans `thinking`, mais aucun texte final ni appel d'outil. La génération avait atteint sa limite avant une action exploitable. L'ancien journal ne conservait pas les métadonnées d'arrêt : il ne permettait pas de diagnostiquer ce cas à lui seul.

L'adaptateur conserve le mode natif du modèle et autorise maintenant **8 192 tokens par génération**, réflexion et réponse comprises. Ce budget est réglable avec `--max-tokens`, entre 256 et 16 384. Un modèle peut prendre davantage de temps pour réfléchir ; le délai par requête passe à 300 secondes. Ce sont des limites, pas des objectifs à atteindre. Voir [les modes de réflexion Ollama](https://docs.ollama.com/capabilities/thinking).

Les journaux conservent désormais la raison d'arrêt et le nombre de tokens générés, sans le texte de réflexion. Une réponse tronquée déclenche une erreur explicite et ses éventuels appels d'outils ne sont pas exécutés. Le budget de tokens par génération est différent de la limite de dix tours de la boucle. Augmenter `--max-tours` n'aurait pas résolu une interruption au premier appel du modèle.

La lecture de plusieurs fichiers était déjà possible : chaque résultat est ajouté à `messages` et conservé pour le tour suivant. Les consignes précisent maintenant qu'un total livraison comprise demande les prix et les conditions de livraison. Le programme utilise les montants actuels des fichiers, y compris vos modifications.
