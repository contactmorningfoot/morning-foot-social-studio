# Morning Foot Social Studio — V1

Application web statique + génération automatique de brouillons Instagram depuis le RSS public de Morning Foot. **Aucun plugin WordPress, Make, Placid ni API d'IA payante.**

## Fonctions
- Lecture du flux `https://morning-foot.com/feed/` toutes les 30 minutes environ via GitHub Actions (horaires non garantis).
- Un brouillon par URL d'article, jusqu'à 120 articles conservés.
- Classification simple (stats, mercato, match, débat), photo RSS si accessible, carte PNG 1080 × 1350 aux couleurs Morning Foot.
- Légende modifiable, question d'engagement, copie et téléchargement PNG.
- Pas de publication automatique sur Instagram. **Les angles sont produits par règles et non par une IA : vérifier la pertinence et les faits.**

## Déploiement sans programmation
1. Créer un compte gratuit GitHub si nécessaire.
2. Créer un dépôt **public** nommé `morning-foot-social-studio`.
3. Décompresser le ZIP puis, dans le dépôt GitHub, cliquer **Add file → Upload files** et glisser **tous les fichiers et dossiers, y compris `.github`**. Attention : certains systèmes masquent `.github` ; vérifier sa présence après l'import.
4. Ouvrir **Settings → Actions → General → Workflow permissions** et sélectionner **Read and write permissions**, puis enregistrer (si ce réglage est disponible).
5. Ouvrir **Actions → Actualiser les posts Morning Foot → Run workflow** pour déclencher la première récupération.
6. Ouvrir **Settings → Pages → Build and deployment**, choisir **Deploy from a branch**, branche `main`, dossier `/docs`, puis **Save**.
7. Patienter quelques minutes et ouvrir l'adresse indiquée par GitHub Pages, normalement `https://VOTRE-IDENTIFIANT.github.io/morning-foot-social-studio/`.

**Important : ce déploiement GitHub Pages est PUBLIC.** Les visuels, légendes et liens sont consultables par toute personne connaissant l'URL. Ne pas y placer de secrets, de contenus confidentiels ou de photos sans droits de republication. Une vraie interface privée avec authentification nécessitera un hébergeur et un contrôle d'accès adaptés (ex. Cloudflare Access) ; ce n'est pas inclus dans cette V1.

## Limites et coûts
- GitHub Actions / Pages peuvent être gratuits dans les limites des offres applicables ; vérifier les quotas et conditions actuels.
- Les tâches planifiées GitHub Actions peuvent être retardées ou désactivées après inactivité du dépôt.
- Le RSS ne fournit pas toujours une photo exploitable ; le visuel bascule alors sur un fond graphique.
- Les images téléchargées doivent être autorisées pour un usage sur Instagram ; vérifier notamment la licence Icon Sport.
- Les titres longs peuvent être tronqués dans le visuel ; relecture recommandée.
- Le script n'analyse pas intégralement les articles : aucune vérification factuelle automatique et aucune IA générative.
- L'interface est statique : les modifications de légende ne sont pas sauvegardées entre sessions.

## Développement local (facultatif)
`pip install -r requirements.txt && python scripts/build.py` puis ouvrir `docs/index.html` via un serveur local. Aucun usage de Python requis pour le déploiement GitHub.
