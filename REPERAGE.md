# Repérer les pictogrammes selon une légende

Le quatrième outil, `reperer_pictogrammes(nom)`, produit une copie PNG annotée
et un rapport JSON dans `annotations/`. Les fichiers sources restent intacts.

## Utilisation

Le rendu utilise Pillow, déjà disponible dans le Python fourni sur ce poste.
Pour une autre installation : `python -m pip install -r requirements.txt`.
Redémarrer le serveur Python après la mise à jour, puis actualiser le chat.
Cliquer sur « Encadrer les stocks » ou demander :

> Repère et encadre les pictogrammes de plan-stocks-entrepot.png selon sa légende.

L'image apparaît dans le chat et s'ouvre en grand en cliquant dessus. Le lien
JSON donne les coordonnées et les associations de labels. Les fichiers générés
sont exclus de Git ; leur suppression manuelle rendra les anciens liens inaccessibles.

## Fonctionnement

1. Le modèle principal choisit `reperer_pictogrammes`.
2. `vision.py` lit le fichier dans documents et appelle Ollama.
3. `reperage.py` localise les zones colorées connexes sur fond clair et attribue
   un identifiant temporaire P1, P2, etc. à chaque candidat.
4. Le VLM lit la légende sur cette image numérotée. Il donne les labels, quantités
   et identifiants P des pictogrammes EXEMPLES de la légende, dans un JSON structuré.
5. Python associe les autres pictogrammes aux exemples par similarité de couleur,
   exclut la région contenant les exemples et valide les boîtes. Pillow trace les
   cadres. Python multiplie les nombres de pictogrammes par les quantités lues.
6. Le serveur affiche l'image et expose le rapport JSON avec les correspondances.

Les identifiants P sont des repères internes. Lorsqu'un CSV de stock est fourni,
un second appel VLM transcrit les identifiants N1/S1 imprimés à côté des pictogrammes
dans une planche de recadrages. La boîte du pictogramme reste indépendante de cette
zone de lecture plus large. Les couleurs, positions et quantités
attendues de notre exemple ne sont pas codées en dur.

Une boîte `[x_min, y_min, x_max, y_max]` est exprimée en pixels, origine en haut
à gauche. Le rapport précise la taille de l'image annotée. Les grandes images
sont réduites à 1536 pixels maximum par côté avant repérage : ces coordonnées
se rapportent à cette image de travail, pas nécessairement à la résolution originale.

## Limites à comprendre

Cette méthode hybride est adaptée aux pictogrammes colorés et séparés sur fond
clair, dont les catégories ont des couleurs distinctes. Elle ne reconnaît pas
la forme indépendamment de la couleur : deux symboles différents de même couleur,
un plan monochrome ou des symboles superposés demandent un autre détecteur.
Les seuils de luminosité, taille et distance de couleur sont des heuristiques.
Un objet décoratif de même couleur peut être confondu avec un pictogramme.

Le VLM peut mal lire la légende ou sélectionner le mauvais exemplaire. Un schéma
JSON valide ne garantit pas sa justesse. Les cadres sont calculés à partir des
pixels colorés et incluent une marge ; ils peuvent déborder légèrement. Les
résultats sont des estimations à vérifier, sans mise à jour de stock réel.

Un pictogramme de pile peut représenter dix produits : la détection compte les
pictogrammes, puis applique la quantité de la légende. Les exemplaires dessinés
dans la légende doivent être exclus. Cette zone est calculée à partir des exemples sélectionnés par le VLM ; une mauvaise sélection peut donc affecter ce filtrage.

Le programme ne contient ni les coordonnées ni les quantités attendues de notre
plan. Pour l'évaluer manuellement, ce plan possède huit piles et huit caisses,
soit 80 carnets et 200 stylos. Comparer surtout les cadres à l'image, pas seulement
les totaux. Les plans sans légende exploitable produisent une erreur explicite.

Tests : `python -m unittest -v tests tests_chat tests_vision tests_reperage`.

Référence : https://docs.ollama.com/capabilities/structured-outputs

## Taux de remplissage depuis le CSV

`reperer_pictogrammes` accepte `fichier_stock` (facultatif). Si ce paramètre est
omis, `stock-reel.csv` est utilisé automatiquement lorsqu'il existe dans documents.
L'outil effectue lui-même la lecture du CSV : le modèle principal ne fournit pas
les quantités ni les pourcentages. Le CSV doit contenir numero,quantite,type_objet.

Pour chaque pictogramme, le VLM transcrit le repère imprimé dans un recadrage
agrandi. Python joint ce repère à la ligne du CSV, vérifie le type de produit,
puis calcule quantité / capacité de la légende × 100 (arrondi à une décimale).
Le nom et le taux apparaissent au-dessus de la boîte, qui contient uniquement
le pictogramme. Les exemples de légende sont exclus. Le rapport JSON conserve
les repères internes P, les identifiants lus, les quantités, capacités et taux.
Les totaux `quantite_theorique` sont explicitement séparés des quantités réelles.

Un identifiant absent, illisible ou dupliqué, un type incompatible ou une capacité
inconnue donne « indisponible », jamais une quantité inventée. Un taux supérieur
à 100 % n'est pas plafonné et est signalé dans le rapport. Le VLM peut encore mal
lire un identifiant ou une capacité : les calculs sont déterministes, la lecture
visuelle reste à vérifier. Cette version suppose les identifiants placés à droite
des icônes, comme sur notre plan ; une autre disposition nécessite d'adapter les recadrages.

Exemple : « Encadre les caisses et les piles sur plan-stocks-entrepot.png et affiche
leur taux de remplissage à partir de stock-reel.csv. »
Résultat vérifié sur le plan fourni : N7 = 7/10 = 70 %, S3 = 1/25 = 4 %.

## Demandes en langage naturel

Le chat et le mode Ollama identifient d'abord l'objectif avec une réponse structurée du LLM : demande d'image, fichier du plan et CSV à utiliser. Aucun test de phrase exacte ni liste de mots-clés ne déclenche le parcours. Pour une annotation, le code exécute ensuite le parcours métier complet et exige un PNG existant avant de répondre. La réponse finale de ce parcours décrit les résultats vérifiés, sans demander au modèle de réinventer les calculs. Les autres questions conservent la boucle d'outils générale. Une ambiguïté sur le fichier donne une demande de précision.

La compréhension reste probabiliste ; le contrat d'exécution évite qu'un objectif d'annotation correctement identifié se termine par un simple inventaire textuel. Ce parcours produit le plan complet avec les taux disponibles ; il ne constitue pas un moteur universel d'édition d'images.
