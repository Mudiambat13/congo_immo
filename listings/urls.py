from django.urls import path

from . import views

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
    path("bien/<str:ref>/", views.detail, name="detail"),
    path("bien/<str:ref>/modifier/", views.modifier, name="modifier"),
    path("bien/<str:ref>/supprimer/", views.supprimer, name="supprimer"),
    path("bien/<str:ref>/statut/", views.changer_statut, name="statut"),
    path("bien/<str:ref>/favori/", views.basculer_favori, name="favori"),
    path("bien/<str:ref>/signaler/", views.signaler, name="signaler"),
    path("bien/<str:ref>/contact/<str:canal>/", views.contact, name="contact"),
    path("bien/<str:ref>/affiche/", views.affiche, name="affiche"),
]
