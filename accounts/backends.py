from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .utils import normaliser_telephone


class EmailOuTelephoneBackend(ModelBackend):
    """Connexion avec l'e-mail ou le numéro de téléphone."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        ident = username.strip()
        user = User.objects.filter(
            Q(email__iexact=ident) | Q(telephone=normaliser_telephone(ident)) | Q(username__iexact=ident)
        ).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
