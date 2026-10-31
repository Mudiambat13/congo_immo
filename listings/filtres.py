from decimal import Decimal, InvalidOperation

from django.db.models import Q

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
    ordre = {"prix_asc": "prix", "prix_desc": "-prix", "populaire": "-vues"}.get(tri, "-cree_le")
    return qs.order_by(ordre, "-id")
