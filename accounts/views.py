from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import ConnexionForm, InscriptionForm, ProfilForm


class Connexion(LoginView):
    template_name = "accounts/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


def inscription(request):
    if request.user.is_authenticated:
        return redirect("listings:mes_annonces")
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailOuTelephoneBackend")
        messages.success(request, "Bienvenue sur Congo Immo. Votre compte est prêt : publiez votre premier bien.")
        return redirect("listings:creer")
    return render(request, "accounts/inscription.html", {"form": form})


@login_required
def profil(request):
    form = ProfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil enregistré.")
        return redirect("accounts:profil")
    return render(request, "accounts/profil.html", {"form": form})
