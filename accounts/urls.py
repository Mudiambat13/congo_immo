from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.Connexion.as_view(), name="connexion"),
    path("deconnexion/", LogoutView.as_view(), name="deconnexion"),
    path("inscription/", views.inscription, name="inscription"),
    path("profil/", views.profil, name="profil"),
]
