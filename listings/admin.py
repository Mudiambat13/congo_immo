from django.contrib import admin

from datetime import timedelta

from django.utils import timezone

from .models import AlerteRecherche, Bien, DemandeVisite, Equipement, Favori, Notification, PhotoBien, PrixHistorique, Province, Quartier, Signalement, Ville


class PhotoInline(admin.TabularInline):
    model = PhotoBien
    extra = 0
    fields = ("image", "ordre")


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ("reference", "objet", "type_annonce", "categorie", "ville", "quartier", "prix", "devise", "statut", "publie", "est_verifie", "photos_dupliquees", "a_la_une_jusqua", "vues", "contacts", "cree_le")
    list_filter = ("type_annonce", "categorie", "statut", "publie", "est_verifie", "photos_dupliquees", "ville__province")
    search_fields = ("reference", "objet", "description", "adresse", "proprietaire__telephone", "proprietaire__email")
    autocomplete_fields = ["quartier"]
    raw_id_fields = ["proprietaire"]
    inlines = [PhotoInline]
    actions = ["verifier", "masquer", "afficher", "mettre_a_la_une", "retirer_une"]
    date_hierarchy = "cree_le"

    @admin.action(description="Marquer comme annonce vérifiée (badge)")
    def verifier(self, request, qs):
        qs.update(est_verifie=True)

    @admin.action(description="Mettre à la une pendant 7 jours")
    def mettre_a_la_une(self, request, qs):
        qs.update(a_la_une_jusqua=timezone.now() + timedelta(days=7))

    @admin.action(description="Retirer de la une")
    def retirer_une(self, request, qs):
        qs.update(a_la_une_jusqua=None)

    @admin.action(description="Masquer du site")
    def masquer(self, request, qs):
        qs.update(publie=False)

    @admin.action(description="Remettre sur le site")
    def afficher(self, request, qs):
        qs.update(publie=True)


@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = ("bien", "motif", "auteur", "traite", "cree_le")
    list_filter = ("traite", "motif")
    actions = ["marquer_traite"]

    @admin.action(description="Marquer comme traité")
    def marquer_traite(self, request, qs):
        qs.update(traite=True)


@admin.register(Quartier)
class QuartierAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville")
    list_filter = ("ville__province",)
    search_fields = ("nom", "ville__nom")


admin.site.register(Province)
admin.site.register(Ville, type("VilleAdmin", (admin.ModelAdmin,), {"list_display": ("nom", "province", "code"), "list_filter": ("province",), "search_fields": ("nom",)}))
admin.site.register(Equipement)
admin.site.register(Favori)


@admin.register(DemandeVisite)
class DemandeVisiteAdmin(admin.ModelAdmin):
    list_display = ("bien", "nom", "telephone", "date_souhaitee", "creneau", "statut", "cree_le")
    list_filter = ("statut", "creneau")
    search_fields = ("nom", "telephone", "bien__reference")


admin.site.register(Notification)
admin.site.register(AlerteRecherche)
admin.site.register(PrixHistorique)
