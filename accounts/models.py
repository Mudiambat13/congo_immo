from django.contrib.auth.models import AbstractUser
from django.db import models

from .utils import formater_telephone, normaliser_telephone


class User(AbstractUser):
    class Role(models.TextChoices):
        PARTICULIER = "particulier", "Propriétaire / particulier"
        COURTIER = "courtier", "Courtier / démarcheur"
        AGENCE = "agence", "Agence immobilière"

    email = models.EmailField("e-mail", unique=True)
    telephone = models.CharField("téléphone", max_length=20, unique=True)
    whatsapp = models.CharField("WhatsApp", max_length=20, blank=True)
    role = models.CharField("profil", max_length=12, choices=Role.choices, default=Role.PARTICULIER)
    bio = models.TextField("présentation", blank=True, max_length=400)
    est_verifie = models.BooleanField("identité vérifiée", default=False)

    REQUIRED_FIELDS = ["email", "telephone"]

    def save(self, *args, **kwargs):
        self.telephone = normaliser_telephone(self.telephone)
        if self.whatsapp:
            self.whatsapp = normaliser_telephone(self.whatsapp)
        super().save(*args, **kwargs)

    @property
    def nom_affiche(self) -> str:
        return self.get_full_name() or self.username

    @property
    def numero_whatsapp(self) -> str:
        return self.whatsapp or self.telephone

    @property
    def telephone_affiche(self) -> str:
        return formater_telephone(self.telephone)

    def __str__(self):
        return self.nom_affiche
