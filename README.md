# Congo Immo

Plateforme web d'annonces immobilières pour toute la RDC : location et vente de maisons, appartements, studios, parcelles, locaux commerciaux, bureaux, entrepôts et concessions.

**Stack : Django (templates) + un peu de JavaScript natif + Leaflet/OpenStreetMap.**
Choix volontaire de ne pas utiliser React : pages rendues côté serveur (légères sur connexion mobile lente), annonces indexables par Google, un seul déploiement, aucun build JS.

## Démarrage rapide

```bash
python -m venv venv && source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_geo          # 26 provinces, 37 villes, quartiers courants, équipements
python manage.py seed_demo         # (facultatif) 10 annonces d'exemple, compte demo@congoimmo.cd / demo1234
python manage.py createsuperuser   # accès à /admin/
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000. Lancer les tests : `python manage.py test` (27 tests).

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
- Pistes : alertes de recherche par WhatsApp/SMS, paiement Mobile Money pour les annonces « à la une », vérification d'identité par pièce, version swahili/lingala, PWA.
- La liste des types de documents est une aide pratique, pas un avis juridique : vérifiez toujours un titre auprès des services compétents.
