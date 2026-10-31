import re
import uuid

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import User
from .utils import normaliser_telephone


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="E-mail ou téléphone",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username", "placeholder": "ex. 0812345678"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "Identifiant ou mot de passe incorrect. Vérifiez l'e-mail ou le numéro saisi.",
        "inactive": "Ce compte est désactivé.",
    }


def _valider_telephone(valeur):
    n = normaliser_telephone(valeur)
    if not re.fullmatch(r"\d{9,15}", n):
        raise forms.ValidationError("Numéro invalide. Exemple : 0812345678 ou +243 81 234 5678.")
    return n


class InscriptionForm(forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmer le mot de passe", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["first_name", "last_name", "telephone", "whatsapp", "email", "role"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "telephone": "Téléphone", "whatsapp": "WhatsApp (si différent)", "email": "E-mail", "role": "Vous êtes"}
        widgets = {
            "telephone": forms.TextInput(attrs={"placeholder": "0812345678", "inputmode": "tel", "autocomplete": "tel"}),
            "whatsapp": forms.TextInput(attrs={"placeholder": "Laisser vide si identique", "inputmode": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_telephone(self):
        n = _valider_telephone(self.cleaned_data["telephone"])
        if User.objects.filter(telephone=n).exists():
            raise forms.ValidationError("Ce numéro a déjà un compte. Connectez-vous plutôt.")
        return n

    def clean_whatsapp(self):
        v = self.cleaned_data.get("whatsapp")
        return _valider_telephone(v) if v else ""

    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Cet e-mail a déjà un compte.")
        return e

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne sont pas identiques.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = f"u{uuid.uuid4().hex[:12]}"
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "telephone", "whatsapp", "role", "bio"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "telephone": "Téléphone", "whatsapp": "WhatsApp", "role": "Vous êtes", "bio": "Présentation (affichée sur vos annonces)"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 3, "placeholder": "Ex. Agence basée à Lubumbashi, biens à Golf et Bel-Air."})}

    def clean_telephone(self):
        n = _valider_telephone(self.cleaned_data["telephone"])
        if User.objects.filter(telephone=n).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce numéro est déjà utilisé par un autre compte.")
        return n

    def clean_whatsapp(self):
        v = self.cleaned_data.get("whatsapp")
        return _valider_telephone(v) if v else ""
