from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Congo Immo : administration"
admin.site.site_title = "Congo Immo"
admin.site.index_title = "Modération et données"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("accounts.urls")),
    path("", include("listings.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "listings.views.page_introuvable"
