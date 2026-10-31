from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CompteAdmin(UserAdmin):
    list_display = ("nom_affiche", "telephone", "email", "role", "est_verifie", "is_active", "date_joined")
    list_filter = ("role", "est_verifie", "is_active")
    search_fields = ("first_name", "last_name", "email", "telephone")
    actions = ["marquer_verifie"]
    fieldsets = UserAdmin.fieldsets + (("Congo Immo", {"fields": ("telephone", "whatsapp", "role", "bio", "est_verifie")}),)

    @admin.action(description="Marquer comme identité vérifiée")
    def marquer_verifie(self, request, queryset):
        queryset.update(est_verifie=True)
