from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Bien


class BienSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    limit = 2000

    def items(self):
        return Bien.objects.filter(publie=True, statut=Bien.Statut.DISPONIBLE).order_by("-modifie_le")

    def lastmod(self, obj):
        return obj.modifie_le


class PagesSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return ["listings:accueil", "listings:louer", "listings:acheter", "listings:carte", "listings:conseils"]

    def location(self, item):
        return reverse(item)


SITEMAPS = {"biens": BienSitemap, "pages": PagesSitemap}
