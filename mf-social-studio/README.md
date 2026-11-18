# Morning Foot Social Studio V2

Détection de fiches statistiques dans les images des articles, classement automatique des sujets et export PNG 1080 × 1350.

## Installation sans programmation

**Important : le dépôt GitHub actuel contient déjà une V1.** Pour éviter tout conflit, utiliser les fichiers de cette archive **à la racine du dépôt** (et non dans un sous-dossier `mf-v2`). Dans GitHub, l'option « Add file > Upload files » ne remplace pas toujours facilement les fichiers imbriqués : il peut être plus simple d'utiliser l'application GitHub Desktop ou l'interface web en créant les chemins indiqués.

1. Ajouter `requirements.txt`, `scripts/build.py`, `docs/index.html`, `docs/posts.json`, `.github/workflows/rss.yml`, `.github/workflows/pages.yml` à la racine du dépôt.
2. Désactiver les anciens workflows RSS et Pages V1 dans Actions pour éviter les écritures concurrentes et les doubles déploiements.
3. Dans Settings > Pages, choisir **GitHub Actions** comme source.
4. Dans Actions, lancer « Actualiser les posts Morning Foot V2 » avec Run workflow.
5. Vérifier la création de `docs/posts.json` et des images `docs/assets`.
6. Lancer « Publier Morning Foot Social Studio V2 » si nécessaire, puis ouvrir l'URL GitHub Pages habituelle.

## Limitations importantes

- Sélection par règles explicites (pas d'IA) : trois sujets maximum par date avec un seuil minimal de 35 points. Ce score est un **indice éditorial heuristique**, pas une prédiction de portée Instagram.
- Les images de type `report-` sont détectées d'après les noms/attributs, pas par reconnaissance visuelle. Certaines fiches peuvent échapper au détecteur.
- Les légendes sont des brouillons extraits de l'article : vérifier les faits et adapter la question avant publication.
- Les crédits DataScout et les droits de republication doivent être vérifiés avant publication.
- Les images sont recopiées dans le dépôt GitHub public, ce qui peut accroître sa taille ; conserver uniquement les fichiers autorisés à la republication.
- GitHub Pages est public : ce n'est pas un espace privé avec authentification.
- GitHub Actions est généralement exécuté à intervalles approximatifs, pas à la minute garantie.
- Pas de publication automatique sur Instagram.
