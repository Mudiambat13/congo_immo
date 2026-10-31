from django.conf import settings


def globaux(request):
    favoris_ids = set()
    if request.user.is_authenticated:
        from .models import Favori
        favoris_ids = set(Favori.objects.filter(utilisateur=request.user).values_list("bien_id", flat=True))
    return {
        "SITE_NOM": settings.SITE_NOM,
        "MAX_PHOTOS": settings.MAX_PHOTOS,
        "favoris_ids": favoris_ids,
    }
