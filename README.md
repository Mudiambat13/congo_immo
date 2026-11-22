# Congo Immo

Plateforme web d'annonces immobilières pour toute la RDC : location et vente de maisons, appartements, studios, parcelles, locaux commerciaux, bureaux, entrepôts et concessions.

**Stack : Django (templates) + un peu de JavaScript natif + Leaflet/OpenStreetMap.**
Choix volontaire de ne pas utiliser React : pages rendues côté serveur (légères sur connexion mobile lente), annonces indexables par Google, un seul déploiement, aucun build JS.

## Démarrage rapide

```bash
python -m venv venv && source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate        # applique aussi la migration 0002 (v2)
python manage.py seed_geo          # 26 provinces, 37 villes, quartiers courants, équipements
python manage.py seed_demo         # (facultatif) 10 annonces d'exemple, compte demo@congoimmo.cd / demo1234
python manage.py createsuperuser   # accès à /admin/
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000. Lancer les tests : `python manage.py test` (48 tests).

## Ce que fait le site

**Pour les annonceurs**
- Inscription avec téléphone (connexion par e-mail **ou** numéro ; formats 0812…, +243 81… acceptés).
- Publication d'un bien en 5 étapes. Le formulaire s'adapte au type d'annonce :
  - *Location* : objet (ex. « Maison locative »), description, chambres/salons/sanitaires, équipements, ville, quartier, référence/adresse (ex. « Avenue Tulipier n°2 »), loyer, devise, **garantie (mois)**, avance, modalités, **jusqu'à 6 photos**.
  - *Vente* : superficie, **type de document disponible** (certificat d'enregistrement, contrat de location, acte de vente, fiche parcellaire…), **position GPS obligatoire**, prix.
- Position GPS : clic sur la carte, repère déplaçable, ou bouton « Utiliser ma position ». Les points hors RDC sont refusés.
- Photos compressées automatiquement (1600 px + miniature 640 px) : chargement rapide en 3G/4G.
- Tableau de bord : vues, contacts, favoris par annonce ; marquer « loué / vendu », retirer, modifier, supprimer.
- **Affiche A4 imprimable avec QR code** (« À LOUER » / « À VENDRE ») à coller sur le portail du bien.

**Pour les chercheurs**
- Recherche par type, ville (toute la RDC, groupée par province), quartier, catégorie, budget, devise, chambres, document, annonceurs vérifiés, mot-clé, tri.
- Vue **liste** ou **carte** (tous les biens géolocalisés).
- Fiche détaillée : galerie, **somme à prévoir à l'entrée** (loyer × (garantie + avance)), **comparaison au prix moyen du quartier**, prix au m² pour les ventes, itinéraire Google Maps.
- Contact direct **WhatsApp** (message pré-rempli avec la référence) ou appel ; partage WhatsApp ; favoris ; signalement d'annonce suspecte.
- Page « Éviter les arnaques ».

**Administration (`/admin/`)**
- Badge « vérifié » (annonce ou annonceur), masquer une annonce, traiter les signalements, gérer provinces, villes, quartiers et équipements.

## Nouveautés de la v2

**Pour chercher**
- **Recherche en une phrase** (accueil) : « maison 3 chambres à Lubumbashi quartier Golf moins de 500 $ » est transformée en filtres (type, catégorie, chambres, ville, quartier, fourchette de prix, devise). Analyse par règles, sans service externe ni clé d'API. Le site affiche ce qu'il a compris.
- **Près de moi** : géolocalisation, rayon de 2 à 50 km, résultats triés par distance.
- **Alertes de recherche** : « Me prévenir des nouvelles annonces » enregistre la recherche (10 maximum par compte). À la publication d'un bien, les personnes concernées reçoivent une notification (cloche dans l'en-tête). E-mail en option : `ALERTES_EMAIL=1` + SMTP.
- **Baisses de prix** : historique du prix, badge « Prix en baisse de X % », rubrique d'accueil, et notification à ceux qui ont le bien en favori.
- **Comparateur** de 3 biens côte à côte (prix, entrée à prévoir, garantie, équipements, indice de confiance), le moins cher est marqué.
- **Carte** avec pastilles de prix et regroupement des biens proches.

**Pour décider**
- **Indice de confiance** (0 à 100) par annonce : photos, GPS, description, conditions claires, annonceur vérifié, annonce contrôlée. Le public voit les points acquis ; le propriétaire voit aussi ce qui lui manque. Ce n'est pas une garantie, et la fiche le dit.
- **Demande de visite** (jour + moment de la journée) : notification au propriétaire, page « Demandes de visite » avec Confirmer / Refuser et bouton WhatsApp pré-rempli. Protection : champ piège anti-robots et 5 demandes par heure et par adresse IP.
- **Galerie plein écran** (glisser, flèches du clavier), partage natif du téléphone.

**Pour les propriétaires**
- **Prix du marché pendant la saisie** : le formulaire indique les prix comparables du quartier (3 annonces minimum) et si votre prix est au-dessus ou en dessous.
- **« Rédiger la description pour moi »** : texte composé à partir des champs remplis.
- **À la une** : champ `a_la_une_jusqua`, action d'administration « Mettre à la une pendant 7 jours » (prêt pour un paiement Mobile Money plus tard).
- **Détection de photos réutilisées** : empreinte perceptuelle de chaque photo ; une photo quasi identique à celle d'un autre annonceur crée un signalement visible **seulement par les modérateurs** (ce n'est pas une preuve : deux agents peuvent légitimement présenter le même bien).

**Design et technique**
- **Mode sombre** automatique (réglage du téléphone) avec bouton clair/sombre.
- **Navigation mobile en bas d'écran** (Accueil, Chercher, Publier, Favoris, Compte) et barre WhatsApp / Appeler / Visite collée en bas des fiches.
- **Application installable (PWA)** : manifeste, icônes, raccourcis ; **les fiches déjà ouvertes restent lisibles hors ligne**, utile quand le réseau coupe.
- **SEO** : `sitemap.xml`, `robots.txt`, données structurées schema.org sur chaque fiche.
- Correctif de sécurité : les redirections `next` sont limitées au site lui-même.

## Notes de production (v2)
- Le plafond de demandes de visite utilise le cache Django. Avec plusieurs processus, configurez un cache partagé (Redis) pour que la limite soit commune.
- La détection de photos compare les empreintes en Python (20 000 photos au maximum) : suffisant pour démarrer ; au-delà, déplacez-la dans une tâche de fond.
- Les alertes sont calculées à la publication, dans la requête : au-delà de quelques milliers d'alertes, passez par une tâche de fond (Celery, RQ).
- Le service worker ne met en cache que les pages `/bien/<référence>/`, les images et les fichiers statiques, jamais l'espace connecté ni l'administration.

## Structure

```
config/        réglages, urls
accounts/      utilisateur personnalisé (téléphone, rôle, vérification), connexion e-mail/téléphone
listings/      modèles (Province, Ville, Quartier, Bien, PhotoBien, Favori, Signalement), formulaires, vues, admin, tests
  management/commands/seed_geo.py, seed_demo.py
templates/     pages (base, accueil, liste, détail, formulaire, tableau de bord, affiche…)
static/        css/app.css, js/app.js
```

## Mise en production

1. Variables d'environnement (voir `.env.example`) : `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, et `DATABASE_URL` pour PostgreSQL (installez `psycopg[binary]`).
2. `python manage.py collectstatic --noinput` puis `gunicorn config.wsgi`.
3. Les fichiers statiques sont servis par WhiteNoise. **Les photos (`media/`) doivent être servies par Nginx** (alias vers `MEDIA_ROOT`) ou par un stockage objet (S3, Cloudflare R2). WhiteNoise ne sert pas `media/`.
4. Sauvegardez régulièrement la base et le dossier `media/`.

## Limites connues et pistes

- Les cartes utilisent les tuiles publiques d'OpenStreetMap : parfait pour démarrer ; en forte audience, prenez un fournisseur de tuiles dédié.
- Le comptage des appels repose sur un clic : indicatif, pas infaillible.
- Pistes : envoi des alertes par WhatsApp/SMS, paiement Mobile Money pour les annonces « à la une », vérification d'identité par pièce, version swahili/lingala, visite virtuelle à 360°.
- La liste des types de documents est une aide pratique, pas un avis juridique : vérifiez toujours un titre auprès des services compétents.
