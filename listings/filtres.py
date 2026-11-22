import math
from decimal import Decimal, InvalidOperation

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from .models import Bien


def biens_publics():
    return (
        Bien.objects.filter(publie=True)
        .select_related("ville__province", "quartier", "proprietaire")
        .prefetch_related("photos")
    )


def _decimal(v):
    try:
        return Decimal(str(v).replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError):
        return None


def appliquer_filtres(qs, p):
    qs = qs.filter(statut=Bien.Statut.DISPONIBLE)
    if p.get("type") in ("location", "vente"):
        qs = qs.filter(type_annonce=p["type"])
    if p.get("categorie") in Bien.Categorie.values:
        qs = qs.filter(categorie=p["categorie"])
    if p.get("province", "").isdigit():
        qs = qs.filter(ville__province_id=int(p["province"]))
    if p.get("ville", "").isdigit():
        qs = qs.filter(ville_id=int(p["ville"]))
    if p.get("quartier"):
        qs = qs.filter(quartier__nom__icontains=p["quartier"].strip())
    if p.get("devise") in Bien.Devise.values:
        qs = qs.filter(devise=p["devise"])
    mini, maxi = _decimal(p.get("prix_min")), _decimal(p.get("prix_max"))
    if mini is not None:
        qs = qs.filter(prix__gte=mini)
    if maxi is not None:
        qs = qs.filter(prix__lte=maxi)
    if p.get("chambres", "").isdigit():
        qs = qs.filter(chambres__gte=int(p["chambres"]))
    if p.get("document") in Bien.Document.values:
        qs = qs.filter(type_document=p["document"])
    if p.get("verifie") == "1":
        qs = qs.filter(Q(est_verifie=True) | Q(proprietaire__est_verifie=True))
    if p.get("gps") == "1":
        qs = qs.filter(latitude__isnull=False)
    q = (p.get("q") or "").strip()
    if q:
        for mot in q.split()[:6]:
            qs = qs.filter(
                Q(objet__icontains=mot) | Q(description__icontains=mot) | Q(adresse__icontains=mot)
                | Q(quartier__nom__icontains=mot) | Q(ville__nom__icontains=mot) | Q(reference__icontains=mot)
            )
    tri = p.get("tri")
    if tri in ("prix_asc", "prix_desc", "populaire"):
        return qs.order_by({"prix_asc": "prix", "prix_desc": "-prix", "populaire": "-vues"}[tri], "-id")
    # Par défaut : les annonces « à la une » d'abord, puis les plus récentes.
    qs = qs.annotate(une=Case(When(a_la_une_jusqua__gt=timezone.now(), then=Value(1)), default=Value(0), output_field=IntegerField()))
    return qs.order_by("-une", "-cree_le", "-id")


def distance_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def lire_position(p):
    """(latitude, longitude, rayon_km) si la requête contient une position valide en RDC, sinon None."""
    try:
        lat, lng = float(p.get("lat")), float(p.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (-14 <= lat <= 6 and 11 <= lng <= 32):
        return None
    rayon = int(p["rayon"]) if str(p.get("rayon", "")).isdigit() and 1 <= int(p["rayon"]) <= 200 else 10
    return lat, lng, rayon


def proches(qs, lat, lng, rayon):
    """Biens géolocalisés dans le rayon, triés du plus proche au plus lointain (attribut distance_km)."""
    dlat = rayon / 111.0
    dlng = rayon / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    res = []
    for b in qs.filter(latitude__range=(lat - dlat, lat + dlat), longitude__range=(lng - dlng, lng + dlng)):
        d = distance_km(lat, lng, float(b.latitude), float(b.longitude))
        if d <= rayon:
            b.distance_km = d
            res.append(b)
    res.sort(key=lambda b: b.distance_km)
    return res
