from django.conf import settings


def globaux(request):
    favoris_ids, nb_notifs = set(), 0
    if request.user.is_authenticated:
        from .models import Favori, Notification
        favoris_ids = set(Favori.objects.filter(utilisateur=request.user).values_list("bien_id", flat=True))
        nb_notifs = Notification.objects.filter(utilisateur=request.user, lu=False).count()
    return {
        "SITE_NOM": settings.SITE_NOM,
        "MAX_PHOTOS": settings.MAX_PHOTOS,
        "favoris_ids": favoris_ids,
        "nb_notifs": nb_notifs,
        "comparaison_refs": request.session.get("comparaison", []),
    }
