import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Avg, Count, Max, Min
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from PIL import Image, ImageOps


class Province(models.Model):
    nom = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Ville(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="villes")
    nom = models.CharField(max_length=80)
    code = models.CharField("code (3 lettres)", max_length=3, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["nom"]
        unique_together = [("province", "nom")]

    def __str__(self):
        return self.nom


class Quartier(models.Model):
    ville = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name="quartiers")
    nom = models.CharField(max_length=80)

    class Meta:
        ordering = ["nom"]
        unique_together = [("ville", "nom")]

    def __str__(self):
        return f"{self.nom} ({self.ville})"


class Equipement(models.Model):
    nom = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


def _chemin_photo(instance, filename):
    return f"biens/{instance.bien_id}/{uuid.uuid4().hex}.jpg"


def _chemin_miniature(instance, filename):
    return f"biens/{instance.bien_id}/m_{uuid.uuid4().hex}.jpg"


class Bien(models.Model):
    class TypeAnnonce(models.TextChoices):
        LOCATION = "location", "À louer"
        VENTE = "vente", "À vendre"

    class Categorie(models.TextChoices):
        MAISON = "maison", "Maison"
        APPARTEMENT = "appartement", "Appartement"
        STUDIO = "studio", "Studio / chambre"
        PARCELLE = "parcelle", "Parcelle / terrain"
        BOUTIQUE = "boutique", "Local commercial / boutique"
        BUREAU = "bureau", "Bureau"
        ENTREPOT = "entrepot", "Entrepôt / hangar"
        CONCESSION = "concession", "Concession / ferme"

    class Devise(models.TextChoices):
        USD = "USD", "USD ($)"
        CDF = "CDF", "CDF (FC)"

    class Document(models.TextChoices):
        CERTIFICAT = "certificat", "Certificat d'enregistrement"
        CONTRAT = "contrat_location", "Contrat de location (concession)"
        ACTE_VENTE = "acte_vente", "Acte de vente"
        FICHE = "fiche_parcellaire", "Fiche parcellaire"
        ATTESTATION = "attestation", "Attestation de propriété / d'attribution"
        LIVRET = "livret_logeur", "Livret de logeur"
        AUTRE = "autre", "Autre document"
        AUCUN = "aucun", "Aucun document pour le moment"

    class Statut(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        CONCLU = "conclu", "Loué / vendu"
        RETIRE = "retire", "Retiré"

    reference = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="biens")
    type_annonce = models.CharField("type d'annonce", max_length=10, choices=TypeAnnonce.choices, default=TypeAnnonce.LOCATION)
    categorie = models.CharField("catégorie", max_length=12, choices=Categorie.choices, default=Categorie.MAISON)
    objet = models.CharField("objet", max_length=120)
    description = models.TextField(max_length=3000)

    ville = models.ForeignKey(Ville, on_delete=models.PROTECT, related_name="biens")
    quartier = models.ForeignKey(Quartier, on_delete=models.SET_NULL, null=True, blank=True, related_name="biens")
    adresse = models.CharField("référence / adresse", max_length=160, help_text="Avenue, numéro, repère connu")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    devise = models.CharField(max_length=3, choices=Devise.choices, default=Devise.USD)
    prix = models.DecimalField("prix / loyer", max_digits=12, decimal_places=2)

    # Location
    garantie_mois = models.PositiveSmallIntegerField("garantie (mois)", null=True, blank=True)
    avance_mois = models.PositiveSmallIntegerField("avance (mois)", null=True, blank=True)
    modalites = models.TextField("modalités", blank=True, max_length=1200)

    # Logement
    chambres = models.PositiveSmallIntegerField(null=True, blank=True)
    salons = models.PositiveSmallIntegerField(null=True, blank=True)
    sanitaires = models.PositiveSmallIntegerField(null=True, blank=True)
    equipements = models.ManyToManyField(Equipement, blank=True, related_name="biens")

    # Vente
    superficie = models.DecimalField("superficie (m²)", max_digits=10, decimal_places=2, null=True, blank=True)
    type_document = models.CharField("document disponible", max_length=20, choices=Document.choices, blank=True)

    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DISPONIBLE)
    publie = models.BooleanField("visible sur le site", default=True)
    est_verifie = models.BooleanField("annonce vérifiée", default=False)
    vues = models.PositiveIntegerField(default=0)
    contacts = models.PositiveIntegerField(default=0)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "bien"
        indexes = [models.Index(fields=["type_annonce", "statut", "publie"])]

    def __str__(self):
        return f"{self.reference or '?'} {self.objet}"

    def save(self, *args, **kwargs):
        creation = self.pk is None
        super().save(*args, **kwargs)
        if creation and not self.reference:
            self.reference = f"CI-{self.ville.code}-{self.pk:05d}"
            super().save(update_fields=["reference"])

    def get_absolute_url(self):
        return reverse("listings:detail", args=[self.reference])

    @property
    def est_location(self):
        return self.type_annonce == self.TypeAnnonce.LOCATION

    @property
    def est_terrain(self):
        return self.categorie in (self.Categorie.PARCELLE, self.Categorie.CONCESSION)

    @property
    def prix_affiche(self):
        return formater_prix(self.prix, self.devise)

    @property
    def entree_total(self):
        """Somme à prévoir à l'entrée : loyer × (garantie + avance)."""
        mois = (self.garantie_mois or 0) + (self.avance_mois or 0)
        if self.est_location and mois:
            return formater_prix(self.prix * mois, self.devise)
        return ""

    @property
    def prix_m2(self):
        if not self.est_location and self.superficie:
            return formater_prix(self.prix / self.superficie, self.devise)
        return ""

    @property
    def couverture(self):
        photos = list(self.photos.all())
        return photos[0] if photos else None

    @property
    def localisation_courte(self):
        return f"{self.quartier.nom}, {self.ville.nom}" if self.quartier else self.ville.nom

    @property
    def a_gps(self):
        return self.latitude is not None and self.longitude is not None

    def statistiques_marche(self):
        """Prix moyen des annonces comparables (même quartier si possible, sinon même ville)."""
        base = Bien.objects.filter(
            publie=True, statut=Bien.Statut.DISPONIBLE, type_annonce=self.type_annonce,
            categorie=self.categorie, devise=self.devise,
        ).exclude(pk=self.pk)
        portee = None
        if self.quartier_id:
            qs = base.filter(quartier=self.quartier)
            if qs.count() >= 3:
                portee, resultat = self.quartier.nom, qs
        if portee is None:
            qs = base.filter(ville=self.ville)
            if qs.count() < 3:
                return None
            portee, resultat = self.ville.nom, qs
        agr = resultat.aggregate(moy=Avg("prix"), mini=Min("prix"), maxi=Max("prix"), n=Count("id"))
        ecart = None
        if agr["moy"]:
            ecart = round((float(self.prix) / float(agr["moy"]) - 1) * 100)
        return {
            "portee": portee, "n": agr["n"], "ecart": ecart,
            "moyenne": formater_prix(agr["moy"], self.devise),
            "mini": formater_prix(agr["mini"], self.devise),
            "maxi": formater_prix(agr["maxi"], self.devise),
        }


def formater_prix(valeur, devise):
    n = f"{round(valeur):,}".replace(",", "\u202f")
    return f"{n}\u00a0{'$' if devise == 'USD' else 'FC'}"


def _optimiser(fichier, cote_max, qualite):
    fichier.seek(0)
    img = ImageOps.exif_transpose(Image.open(fichier)).convert("RGB")
    img.thumbnail((cote_max, cote_max))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=qualite, optimize=True, progressive=True)
    return ContentFile(buf.getvalue())


class PhotoBien(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=_chemin_photo)
    miniature = models.ImageField(upload_to=_chemin_miniature, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "id"]

    def save(self, *args, **kwargs):
        # Compression automatique : photos légères pour les connexions mobiles.
        if self._state.adding and self.image and not self.image._committed:
            source = self.image.file
            grande = _optimiser(source, 1600, 80)
            petite = _optimiser(source, 640, 74)
            self.image.save("p.jpg", grande, save=False)
            self.miniature.save("m.jpg", petite, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Photo {self.pk} de {self.bien_id}"


@receiver(post_delete, sender=PhotoBien)
def _supprimer_fichiers(sender, instance, **kwargs):
    for champ in (instance.image, instance.miniature):
        if champ:
            champ.delete(save=False)


class Favori(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favoris")
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="favoris")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("utilisateur", "bien")]
        ordering = ["-cree_le"]


class Signalement(models.Model):
    class Motif(models.TextChoices):
        ARNAQUE = "arnaque", "Suspicion d'arnaque"
        INDISPONIBLE = "indisponible", "Bien déjà loué ou vendu"
        PRIX = "prix", "Prix ou informations faux"
        PHOTOS = "photos", "Photos qui ne correspondent pas"
        AUTRE = "autre", "Autre"

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="signalements")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    motif = models.CharField(max_length=14, choices=Motif.choices)
    message = models.TextField(blank=True, max_length=500)
    traite = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["traite", "-cree_le"]
