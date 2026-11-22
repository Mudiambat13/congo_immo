from django.urls import path

from . import views, views_plus

app_name = "listings"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("biens/", views.liste, name="liste"),
    path("louer/", views.liste, {"type_annonce": "location"}, name="louer"),
    path("acheter/", views.liste, {"type_annonce": "vente"}, name="acheter"),
    path("carte/", views.liste, {"vue": "carte"}, name="carte"),
    path("api/biens.geojson", views.geojson, name="geojson"),
    path("api/quartiers/", views.api_quartiers, name="api_quartiers"),
    path("publier/", views.creer, name="creer"),
    path("mes-annonces/", views.mes_annonces, name="mes_annonces"),
    path("favoris/", views.mes_favoris, name="favoris"),
    path("conseils/", views.conseils, name="conseils"),
    path("agent/<int:pk>/", views.profil_public, name="profil_public"),
    path("recherche/", views_plus.recherche_intelligente, name="recherche"),
    path("comparer/", views_plus.comparer, name="comparer"),
    path("comparer/vider/", views_plus.vider_comparaison, name="vider_comparaison"),
    path("comparer/<str:ref>/", views_plus.basculer_comparaison, name="basculer_comparaison"),
    path("alertes/", views_plus.mes_alertes, name="alertes"),
    path("alertes/sauvegarder/", views_plus.sauvegarder_recherche, name="sauvegarder_recherche"),
    path("alertes/<int:pk>/", views_plus.action_alerte, name="action_alerte"),
    path("notifications/", views_plus.notifications, name="notifications"),
    path("visites/", views_plus.visites_recues, name="visites"),
    path("visites/<int:pk>/statut/", views_plus.statut_visite, name="statut_visite"),
    path("api/marche/", views_plus.api_marche, name="api_marche"),
    path("manifest.webmanifest", views_plus.manifest, name="manifest"),
    path("sw.js", views_plus.service_worker, name="sw"),
    path("hors-ligne/", views_plus.hors_ligne, name="hors_ligne"),
    path("robots.txt", views_plus.robots, name="robots"),
    path("bien/<str:ref>/", views.detail, name="detail"),
    path("bien/<str:ref>/visite/", views_plus.demander_visite, name="visite"),
    path("bien/<str:ref>/modifier/", views.modifier, name="modifier"),
    path("bien/<str:ref>/supprimer/", views.supprimer, name="supprimer"),
    path("bien/<str:ref>/statut/", views.changer_statut, name="statut"),
    path("bien/<str:ref>/favori/", views.basculer_favori, name="favori"),
    path("bien/<str:ref>/signaler/", views.signaler, name="signaler"),
    path("bien/<str:ref>/contact/<str:canal>/", views.contact, name="contact"),
    path("bien/<str:ref>/affiche/", views.affiche, name="affiche"),
]
