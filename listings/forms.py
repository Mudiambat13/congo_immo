from django import forms
from django.conf import settings

from .models import Bien, Equipement, PhotoBien, Province, Quartier, Signalement, Ville


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*", "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        un = super().clean
        if isinstance(data, (list, tuple)):
            return [un(d, initial) for d in data if d]
        return [un(data, initial)] if data else []


class VilleSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opt = super().create_option(name, value, label, selected, index, subindex, attrs)
        inst = getattr(value, "instance", None)
        if inst is not None:
            opt["attrs"].update({"data-province": inst.province_id, "data-lat": inst.latitude, "data-lng": inst.longitude})
        return opt


class BienForm(forms.ModelForm):
    province = forms.ModelChoiceField(Province.objects.all(), required=False, label="Province", empty_label="Choisir la province")
    quartier_nom = forms.CharField(
        label="Quartier", max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "ex. Bel-Air", "list": "liste-quartiers", "autocomplete": "off"}),
    )
    photos_nouvelles = MultipleImageField(required=False, label="Photos")
    photos_a_supprimer = forms.ModelMultipleChoiceField(
        PhotoBien.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, label="Photos à retirer"
    )

    class Meta:
        model = Bien
        fields = [
            "type_annonce", "categorie", "objet", "description", "ville", "adresse", "latitude", "longitude",
            "devise", "prix", "garantie_mois", "avance_mois", "modalites",
            "chambres", "salons", "sanitaires", "equipements", "superficie", "type_document",
        ]
        widgets = {
            "type_annonce": forms.RadioSelect,
            "objet": forms.TextInput(attrs={"placeholder": "ex. Maison locative"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "ex. 2 chambres, salon, sanitaire interne, cour carrelée, quartier calme"}),
            "ville": VilleSelect,
            "adresse": forms.TextInput(attrs={"placeholder": "ex. Avenue Tulipier n°2, près de l'église"}),
            "latitude": forms.TextInput(attrs={"readonly": True, "placeholder": "Cliquez sur la carte"}),
            "longitude": forms.TextInput(attrs={"readonly": True, "placeholder": "Cliquez sur la carte"}),
            "prix": forms.NumberInput(attrs={"min": 0, "step": "any", "inputmode": "decimal"}),
            "garantie_mois": forms.NumberInput(attrs={"min": 0, "max": 36, "placeholder": "ex. 3"}),
            "avance_mois": forms.NumberInput(attrs={"min": 0, "max": 36, "placeholder": "ex. 1"}),
            "modalites": forms.Textarea(attrs={"rows": 3, "placeholder": "ex. Loyer payable le 5 de chaque mois, bail d'un an, visite sur rendez-vous"}),
            "chambres": forms.NumberInput(attrs={"min": 0, "max": 50}),
            "salons": forms.NumberInput(attrs={"min": 0, "max": 20}),
            "sanitaires": forms.NumberInput(attrs={"min": 0, "max": 20}),
            "superficie": forms.NumberInput(attrs={"min": 1, "step": "any", "placeholder": "ex. 375"}),
            "equipements": forms.CheckboxSelectMultiple,
            "type_document": forms.Select,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ville"].queryset = Ville.objects.select_related("province")
        self.fields["ville"].empty_label = "Choisir la ville"
        self.fields["equipements"].queryset = Equipement.objects.all()
        self.fields["equipements"].required = False
        self.fields["type_document"].choices = [("", "Choisir le document")] + list(Bien.Document.choices)
        self.fields["type_document"].required = False
        self.fields["description"].required = True
        self.fields["adresse"].required = True
        if self.instance.pk:
            self.fields["photos_a_supprimer"].queryset = self.instance.photos.all()
            if self.instance.ville_id:
                self.fields["province"].initial = self.instance.ville.province_id
            if self.instance.quartier_id:
                self.fields["quartier_nom"].initial = self.instance.quartier.nom

    def clean_photos_nouvelles(self):
        fichiers = self.cleaned_data.get("photos_nouvelles") or []
        limite = settings.MAX_TAILLE_PHOTO_MO * 1024 * 1024
        for f in fichiers:
            if f.size > limite:
                raise forms.ValidationError(f"« {f.name} » dépasse {settings.MAX_TAILLE_PHOTO_MO} Mo. Réduisez la photo et réessayez.")
        return fichiers

    def clean(self):
        data = super().clean()
        type_annonce = data.get("type_annonce")
        categorie = data.get("categorie")
        terrain = categorie in (Bien.Categorie.PARCELLE, Bien.Categorie.CONCESSION)

        prix = data.get("prix")
        if prix is not None and prix <= 0:
            self.add_error("prix", "Indiquez un montant supérieur à zéro.")

        if type_annonce == Bien.TypeAnnonce.VENTE:
            if not data.get("superficie"):
                self.add_error("superficie", "Indiquez la superficie en m² pour une vente.")
            if not data.get("type_document"):
                self.add_error("type_document", "Précisez le document disponible, même « Aucun ».")
            if data.get("latitude") is None or data.get("longitude") is None:
                self.add_error("latitude", "Pour une vente, placez le bien sur la carte (GPS).")
        else:
            if data.get("garantie_mois") is None:
                self.add_error("garantie_mois", "Indiquez le nombre de mois de garantie (0 si aucune).")
            data["superficie"] = data.get("superficie")

        lat, lng = data.get("latitude"), data.get("longitude")
        if (lat is None) != (lng is None):
            self.add_error("latitude", "Latitude et longitude vont ensemble.")
        if lat is not None and not (-14 <= float(lat) <= 6):
            self.add_error("latitude", "Ce point est hors de la RDC. Déplacez le repère sur la carte.")
        if lng is not None and not (11 <= float(lng) <= 32):
            self.add_error("longitude", "Ce point est hors de la RDC. Déplacez le repère sur la carte.")

        if not terrain and type_annonce and data.get("chambres") is None and categorie in (Bien.Categorie.MAISON, Bien.Categorie.APPARTEMENT, Bien.Categorie.STUDIO):
            self.add_error("chambres", "Indiquez le nombre de chambres.")

        # Photos : 1 minimum, 6 maximum au total
        existantes = self.instance.photos.count() if self.instance.pk else 0
        retirees = len(data.get("photos_a_supprimer") or [])
        nouvelles = len(data.get("photos_nouvelles") or [])
        total = existantes - retirees + nouvelles
        if total < 1:
            self.add_error("photos_nouvelles", "Ajoutez au moins une photo : les annonces avec photos reçoivent beaucoup plus de contacts.")
        elif total > settings.MAX_PHOTOS:
            self.add_error("photos_nouvelles", f"Maximum {settings.MAX_PHOTOS} photos par bien (vous en avez {total}).")
        return data

    def save(self, proprietaire=None, commit=True):
        bien = super().save(commit=False)
        if proprietaire is not None:
            bien.proprietaire = proprietaire
        nom = " ".join(self.cleaned_data["quartier_nom"].split())
        quartier = Quartier.objects.filter(ville=bien.ville, nom__iexact=nom).first()
        if quartier is None:
            quartier = Quartier.objects.create(ville=bien.ville, nom=nom[:1].upper() + nom[1:])
        bien.quartier = quartier
        if bien.est_location is False:
            bien.garantie_mois = bien.avance_mois = None
            bien.modalites = bien.modalites or ""
        else:
            bien.type_document = ""
        if commit:
            bien.save()
            self.save_m2m()
            for p in self.cleaned_data.get("photos_a_supprimer") or []:
                p.delete()
            debut = bien.photos.count()
            for i, f in enumerate(self.cleaned_data.get("photos_nouvelles") or []):
                PhotoBien.objects.create(bien=bien, image=f, ordre=debut + i)
        return bien


class SignalementForm(forms.ModelForm):
    class Meta:
        model = Signalement
        fields = ["motif", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3, "placeholder": "Dites-nous ce qui ne va pas (facultatif)"})}
