import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Avg, Count, Max, Min
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
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
    photos_dupliquees = models.BooleanField("photos déjà vues dans une autre annonce", default=False)
    a_la_une_jusqua = models.DateTimeField("à la une jusqu'au", null=True, blank=True)
    prix_avant_baisse = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    prix_baisse_le = models.DateTimeField(null=True, blank=True, editable=False)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prix_orig = self.__dict__.get("prix") if self.pk else None

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._prix_orig = self.__dict__.get("prix")

    def save(self, *args, **kwargs):
        creation = self.pk is None
        ancien = None if creation else self._prix_orig
        change = baisse = False
        if ancien is not None and self.prix is not None and Decimal(str(ancien)) != Decimal(str(self.prix)):
            change = True
            if Decimal(str(self.prix)) < Decimal(str(ancien)):
                baisse = True
                self.prix_avant_baisse, self.prix_baisse_le = ancien, timezone.now()
            else:
                self.prix_avant_baisse = self.prix_baisse_le = None
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(kwargs["update_fields"]) + ["prix_avant_baisse", "prix_baisse_le"]
        super().save(*args, **kwargs)
        if change:
            PrixHistorique.objects.create(bien=self, ancien_prix=ancien, nouveau_prix=self.prix)
            if baisse:
                from .services import notifier_baisse_prix
                notifier_baisse_prix(self, ancien)
        self._prix_orig = self.prix
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

    @property
    def est_a_la_une(self):
        return bool(self.a_la_une_jusqua and self.a_la_une_jusqua > timezone.now())

    @property
    def est_nouveau(self):
        return bool(self.cree_le and timezone.now() - self.cree_le < timedelta(days=3))

    @property
    def baisse_pct(self):
        if self.prix_baisse_le and self.prix_avant_baisse and self.prix < self.prix_avant_baisse \
                and timezone.now() - self.prix_baisse_le < timedelta(days=30):
            return round((1 - float(self.prix) / float(self.prix_avant_baisse)) * 100)
        return None

    @property
    def prix_avant_affiche(self):
        return formater_prix(self.prix_avant_baisse, self.devise) if self.prix_avant_baisse else ""

    @property
    def prix_court(self):
        return prix_court(self.prix, self.devise)

    def confiance(self):
        """Indice de confiance sur 100, calculé à partir des informations fournies. Ce n'est pas une garantie."""
        nb = len(list(self.photos.all()))
        if self.est_location:
            if self.garantie_mois is not None and self.modalites:
                cond, cond_lib, cond_conseil = 15, "Garantie et modalités indiquées", "Indiquez la garantie et les modalités de paiement."
            elif self.garantie_mois is not None:
                cond, cond_lib, cond_conseil = 8, "Garantie indiquée", "Ajoutez les modalités de paiement pour gagner des points."
            else:
                cond, cond_lib, cond_conseil = 0, "Garantie et modalités indiquées", "Indiquez la garantie et les modalités de paiement."
        else:
            ok = self.type_document not in ("", self.Document.AUCUN)
            cond, cond_lib, cond_conseil = (15 if ok else 0), "Document de propriété indiqué", "Précisez le document disponible (certificat, acte de vente...)."
        items = [
            ("Photos nombreuses", 25 if nb >= 5 else 20 if nb >= 3 else 10 if nb >= 1 else 0, 25, "Ajoutez au moins 5 photos : façade, pièces, sanitaire, cour."),
            ("Position GPS", 15 if self.a_gps else 0, 15, "Placez le bien sur la carte pour que les visiteurs le trouvent."),
            ("Description détaillée", 10 if len(self.description or "") >= 80 else 0, 10, "Décrivez le bien en 80 caractères ou plus."),
            (cond_lib, cond, 15, cond_conseil),
            ("Annonceur vérifié par l'équipe", 20 if self.proprietaire.est_verifie else 0, 20, "Faites vérifier votre identité par l'équipe Congo Immo."),
            ("Annonce contrôlée par l'équipe", 10 if self.est_verifie else 0, 10, "Une annonce complète peut être contrôlée par l'équipe."),
            ("Photos jamais vues ailleurs sur le site", 0 if self.photos_dupliquees else 5, 5, "Utilisez vos propres photos, prises sur place."),
        ]
        criteres = [{"libelle": n, "gagne": g, "max": m, "ok": g == m, "conseil": c, "a_gagner": m - g} for n, g, m, c in items]
        score = sum(c["gagne"] for c in criteres)
        niveau = ("Très complète", "haut") if score >= 80 else ("Bien renseignée", "moyen") if score >= 55 else ("À compléter", "bas")
        return {"score": score, "niveau": niveau[0], "classe": niveau[1], "criteres": criteres, "manquants": [c for c in criteres if not c["ok"]]}

    def detecter_photos_dupliquees(self):
        """Signale (aux modérateurs seulement) une photo quasi identique à celle d'un autre annonceur."""
        mes = [p.empreinte for p in self.photos.all() if p.empreinte]
        if not mes:
            return False
        autres = PhotoBien.objects.exclude(bien__proprietaire_id=self.proprietaire_id).exclude(empreinte="") \
            .values_list("empreinte", "bien__reference")[:20000]
        trouve = None
        for h, ref in autres:
            if any(bin(int(h, 16) ^ int(m, 16)).count("1") <= 6 for m in mes):
                trouve = ref
                break
        trouve_bool = trouve is not None
        if trouve_bool != self.photos_dupliquees:
            Bien.objects.filter(pk=self.pk).update(photos_dupliquees=trouve_bool)
            self.photos_dupliquees = trouve_bool
        if trouve_bool and not self.signalements.filter(auteur__isnull=True, motif="photos", traite=False).exists():
            Signalement.objects.create(bien=self, motif="photos", message=f"Détection automatique : une photo ressemble à celle de l'annonce {trouve}.")
        return trouve_bool

    @classmethod
    def stats_marche(cls, type_annonce, categorie, devise, ville_id, quartier_id=None, exclude_pk=None):
        """Prix des annonces comparables : même quartier si 3 annonces ou plus, sinon même ville."""
        base = cls.objects.filter(publie=True, statut=cls.Statut.DISPONIBLE, type_annonce=type_annonce, categorie=categorie, devise=devise)
        if exclude_pk:
            base = base.exclude(pk=exclude_pk)
        portee = resultat = None
        if quartier_id:
            qs = base.filter(quartier_id=quartier_id)
            if qs.count() >= 3:
                portee, resultat = Quartier.objects.get(pk=quartier_id).nom, qs
        if resultat is None:
            qs = base.filter(ville_id=ville_id)
            if qs.count() < 3:
                return None
            portee, resultat = Ville.objects.get(pk=ville_id).nom, qs
        agr = resultat.aggregate(moy=Avg("prix"), mini=Min("prix"), maxi=Max("prix"), n=Count("id"))
        return {"portee": portee, "n": agr["n"], "moy": float(agr["moy"]), "mini": float(agr["mini"]), "maxi": float(agr["maxi"])}

    def statistiques_marche(self):
        st = Bien.stats_marche(self.type_annonce, self.categorie, self.devise, self.ville_id, self.quartier_id, exclude_pk=self.pk)
        if not st:
            return None
        return {
            "portee": st["portee"], "n": st["n"], "ecart": round((float(self.prix) / st["moy"] - 1) * 100),
            "moyenne": formater_prix(st["moy"], self.devise), "mini": formater_prix(st["mini"], self.devise), "maxi": formater_prix(st["maxi"], self.devise),
        }


def prix_court(valeur, devise):
    v = float(valeur)
    sym = "$" if devise == "USD" else "FC"
    if v >= 1_000_000:
        t = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".") + " M"
    elif v >= 10_000:
        t = f"{v / 1000:.0f} k"
    else:
        t = f"{v:.0f}"
    return f"{t} {sym}"


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


def empreinte_image(fichier):
    """Empreinte perceptuelle (dHash 64 bits) : deux copies d'une même photo ont des empreintes voisines."""
    try:
        fichier.seek(0)
        img = ImageOps.exif_transpose(Image.open(fichier)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    except Exception:
        return ""
    px = list(img.getdata())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    n = bin(bits).count("1")
    return f"{bits:016x}" if 8 <= n <= 56 else ""  # images quasi unies : empreinte inutilisable


class PhotoBien(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=_chemin_photo)
    miniature = models.ImageField(upload_to=_chemin_miniature, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)
    empreinte = models.CharField(max_length=16, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["ordre", "id"]

    def save(self, *args, **kwargs):
        # Compression automatique : photos légères pour les connexions mobiles.
        if self._state.adding and self.image and not self.image._committed:
            source = self.image.file
            self.empreinte = empreinte_image(source)
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


class PrixHistorique(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="historique_prix")
    ancien_prix = models.DecimalField(max_digits=12, decimal_places=2)
    nouveau_prix = models.DecimalField(max_digits=12, decimal_places=2)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]


class Notification(models.Model):
    class Type(models.TextChoices):
        ALERTE = "alerte", "Nouvelle annonce"
        BAISSE = "baisse", "Baisse de prix"
        VISITE = "visite", "Demande de visite"

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=10, choices=Type.choices)
    titre = models.CharField(max_length=160)
    message = models.CharField(max_length=300, blank=True)
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    url = models.CharField(max_length=200, blank=True, default="")
    lu = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]

    @property
    def lien(self):
        if self.url:
            return self.url
        return self.bien.get_absolute_url() if self.bien_id else reverse("listings:accueil")


class AlerteRecherche(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alertes")
    parametres = models.CharField(max_length=500)
    active = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]

    @property
    def resume(self):
        from django.http import QueryDict
        from .services import resumer_params
        return ", ".join(resumer_params(QueryDict(self.parametres))) or "Toutes les annonces"

    @property
    def lien(self):
        return f"{reverse('listings:liste')}?{self.parametres}"


class DemandeVisite(models.Model):
    class Creneau(models.TextChoices):
        MATIN = "matin", "Matin (8h à 12h)"
        APRES_MIDI = "apres_midi", "Après-midi (12h à 16h)"
        SOIR = "soir", "Fin d'après-midi (16h à 18h)"

    class Statut(models.TextChoices):
        ATTENTE = "attente", "En attente"
        CONFIRMEE = "confirmee", "Confirmée"
        REFUSEE = "refusee", "Refusée"

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="visites")
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    nom = models.CharField(max_length=80)
    telephone = models.CharField(max_length=20)
    date_souhaitee = models.DateField()
    creneau = models.CharField(max_length=12, choices=Creneau.choices)
    message = models.CharField(max_length=300, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ATTENTE)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["statut", "date_souhaitee", "-cree_le"]

    @property
    def lien_whatsapp(self):
        quand = f"{self.date_souhaitee:%d/%m/%Y}, {self.get_creneau_display().lower()}"
        if self.statut == self.Statut.CONFIRMEE:
            texte = f"Bonjour {self.nom}, votre visite de « {self.bien.objet} » ({self.bien.reference}) est confirmée le {quand}. À bientôt."
        elif self.statut == self.Statut.REFUSEE:
            texte = f"Bonjour {self.nom}, je ne peux pas vous recevoir le {quand} pour « {self.bien.objet} ». Proposez-moi un autre jour."
        else:
            texte = f"Bonjour {self.nom}, j'ai bien reçu votre demande de visite pour « {self.bien.objet} » le {quand}."
        return f"https://wa.me/{self.telephone}?text={quote(texte)}"
