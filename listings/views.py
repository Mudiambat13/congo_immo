import json
from datetime import timedelta
from urllib.parse import quote

import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .filtres import appliquer_filtres, biens_publics, lire_position, proches
from .forms import BienForm, SignalementForm, VisiteForm
from .services import notifier_alertes
from .models import Bien, DemandeVisite, Favori, Province, Quartier, Ville

User = get_user_model()


def page_introuvable(request, exception=None):
    return render(request, "404.html", status=404)


def accueil(request):
    base = biens_publics().filter(statut=Bien.Statut.DISPONIBLE)
    villes = (
        Ville.objects.annotate(n=Count("biens", filter=Q(biens__publie=True, biens__statut="disponible")))
        .filter(n__gt=0).order_by("-n")[:8]
    )
    contexte = {
        "a_la_une": base.filter(a_la_une_jusqua__gt=timezone.now())[:6],
        "baisses": base.filter(prix_baisse_le__gte=timezone.now() - timedelta(days=30), prix_avant_baisse__isnull=False)[:6],
        "a_louer": base.filter(type_annonce="location")[:6],
        "a_vendre": base.filter(type_annonce="vente")[:6],
        "villes_populaires": villes,
        "nb_biens": base.count(),
        "nb_villes": Ville.objects.filter(biens__publie=True).distinct().count(),
        "nb_proprietaires": base.values("proprietaire").distinct().count(),
        "provinces": Province.objects.prefetch_related("villes"),
        "categories": Bien.Categorie.choices,
    }
    return render(request, "listings/accueil.html", contexte)


def _retour(request, defaut):
    """Redirection sûre : seulement vers ce même site."""
    suivant = request.POST.get("next") or ""
    if suivant and url_has_allowed_host_and_scheme(suivant, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(suivant)
    return redirect(defaut)


def liste(request, type_annonce=None, vue=None):
    params = request.GET.copy()
    if type_annonce:
        params["type"] = type_annonce
    qs = appliquer_filtres(biens_publics(), params)
    pos = lire_position(params)
    resultats = proches(qs, *pos) if pos else qs
    page = Paginator(resultats, 12).get_page(params.get("page"))
    titre = {"location": "Biens à louer", "vente": "Biens à vendre"}.get(params.get("type"), "Tous les biens")
    vue = vue or params.get("vue")
    filtres_actifs = any(params.get(k) for k in ("categorie", "province", "ville", "quartier", "prix_min", "prix_max", "chambres", "document", "verifie", "q", "devise")) or bool(pos)
    contexte = {
        "page": page, "total": page.paginator.count, "titre": titre, "p": params,
        "vue": "carte" if vue == "carte" else "liste",
        "provinces": Province.objects.prefetch_related("villes"),
        "categories": Bien.Categorie.choices,
        "documents": Bien.Document.choices,
        "type_fixe": type_annonce,
        "filtres_actifs": filtres_actifs,
        "position": {"lat": pos[0], "lng": pos[1], "rayon": pos[2]} if pos else None,
        "rayons": (2, 5, 10, 25, 50),
    }
    return render(request, "listings/liste.html", contexte)


def geojson(request):
    qs = appliquer_filtres(biens_publics(), request.GET).filter(latitude__isnull=False)[:500]
    features = []
    for b in qs:
        c = b.couverture
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(b.longitude), float(b.latitude)]},
            "properties": {
                "ref": b.reference, "objet": b.objet, "prix": b.prix_affiche, "court": b.prix_court, "une": b.est_a_la_une, "location": b.est_location,
                "lieu": b.localisation_courte, "url": b.get_absolute_url(),
                "image": c.miniature.url if c and c.miniature else (c.image.url if c else ""),
                "detail": f"{b.chambres} ch." if b.chambres else (f"{float(b.superficie):g} m²" if b.superficie else ""),
            },
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})


def api_quartiers(request):
    ville = request.GET.get("ville", "")
    if not ville.isdigit():
        return JsonResponse({"quartiers": []})
    noms = list(Quartier.objects.filter(ville_id=int(ville)).values_list("nom", flat=True))
    return JsonResponse({"quartiers": noms})


def _charger_bien(ref):
    return get_object_or_404(
        Bien.objects.select_related("ville__province", "quartier", "proprietaire").prefetch_related("photos", "equipements"),
        reference=ref,
    )


def _jsonld(request, b):
    """Données structurées schema.org : Google peut afficher le prix et les photos dans ses résultats."""
    data = {
        "@context": "https://schema.org", "@type": "RealEstateListing", "name": b.objet, "description": b.description[:300],
        "url": request.build_absolute_uri(b.get_absolute_url()), "datePosted": b.cree_le.date().isoformat(),
        "image": [request.build_absolute_uri(p.image.url) for p in b.photos.all()],
        "offers": {"@type": "Offer", "price": str(int(b.prix)), "priceCurrency": b.devise,
                   "availability": "https://schema.org/InStock" if b.statut == Bien.Statut.DISPONIBLE else "https://schema.org/SoldOut"},
        "address": {"@type": "PostalAddress", "streetAddress": b.adresse, "addressLocality": b.ville.nom, "addressRegion": b.ville.province.nom, "addressCountry": "CD"},
    }
    if b.a_gps:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": float(b.latitude), "longitude": float(b.longitude)}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def rendre_detail(request, bien, form_visite=None, form_signal=None):
    est_proprio = request.user.is_authenticated and request.user == bien.proprietaire
    if form_visite is None:
        initial = {"nom": request.user.nom_affiche, "telephone": request.user.telephone} if request.user.is_authenticated else {}
        form_visite = VisiteForm(initial=initial)
    dispo = bien.statut == Bien.Statut.DISPONIBLE and bien.publie
    similaires = (
        biens_publics().filter(statut=Bien.Statut.DISPONIBLE, ville=bien.ville, type_annonce=bien.type_annonce)
        .exclude(pk=bien.pk)[:3]
    )
    contexte = {
        "b": bien, "est_proprio": est_proprio, "similaires": similaires,
        "marche": bien.statistiques_marche() if dispo else None,
        "form_signal": form_signal or SignalementForm(), "form_visite": form_visite,
        "doc_label": bien.get_type_document_display() if bien.type_document else "",
        "confiance": bien.confiance(), "historique": list(bien.historique_prix.all()[:5]),
        "jsonld": _jsonld(request, bien), "photos_json": json.dumps([p.image.url for p in bien.photos.all()]),
        "peut_visiter": dispo,
    }
    return render(request, "listings/detail.html", contexte)


def detail(request, ref):
    bien = _charger_bien(ref)
    est_proprio = request.user.is_authenticated and request.user == bien.proprietaire
    if (not bien.publie or bien.statut == Bien.Statut.RETIRE) and not (est_proprio or request.user.is_staff):
        raise Http404
    vus = request.session.get("vus", [])
    if bien.pk not in vus and not est_proprio:
        Bien.objects.filter(pk=bien.pk).update(vues=F("vues") + 1)
        request.session["vus"] = (vus + [bien.pk])[-200:]
    return rendre_detail(request, bien)


@login_required
def creer(request):
    form = BienForm(request.POST or None, request.FILES or None, initial={"type_annonce": request.GET.get("type") or "location"})
    if request.method == "POST" and form.is_valid():
        bien = form.save(proprietaire=request.user)
        notifier_alertes(bien)
        messages.success(request, f"Annonce publiée. Référence {bien.reference} : imprimez l'affiche à coller sur le bien.")
        return redirect(bien)
    return render(request, "listings/formulaire.html", {"form": form, "mode": "creation", "villes": Ville.objects.all()})


@login_required
def modifier(request, ref):
    bien = get_object_or_404(Bien, reference=ref, proprietaire=request.user)
    form = BienForm(request.POST or None, request.FILES or None, instance=bien)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modifications enregistrées.")
        return redirect(bien)
    return render(request, "listings/formulaire.html", {"form": form, "mode": "edition", "bien": bien, "villes": Ville.objects.all()})


@login_required
def supprimer(request, ref):
    bien = get_object_or_404(Bien, reference=ref, proprietaire=request.user)
    if request.method == "POST":
        bien.delete()
        messages.success(request, "Annonce supprimée.")
        return redirect("listings:mes_annonces")
    return render(request, "listings/supprimer.html", {"b": bien})


@login_required
@require_POST
def changer_statut(request, ref):
    bien = get_object_or_404(Bien, reference=ref, proprietaire=request.user)
    nouveau = request.POST.get("statut")
    if nouveau in Bien.Statut.values:
        bien.statut = nouveau
        bien.save(update_fields=["statut", "modifie_le"])
        libelle = {"disponible": "remise en ligne", "conclu": "marquée comme " + ("louée" if bien.est_location else "vendue"), "retire": "retirée du site"}[nouveau]
        messages.success(request, f"Annonce {libelle}.")
    return _retour(request, "listings:mes_annonces")


@login_required
def mes_annonces(request):
    biens = (
        Bien.objects.filter(proprietaire=request.user)
        .select_related("ville", "quartier").prefetch_related("photos")
        .annotate(nb_favoris=Count("favoris", distinct=True))
    )
    totaux = {
        "vues": sum(b.vues for b in biens),
        "contacts": sum(b.contacts for b in biens),
        "favoris": sum(b.nb_favoris for b in biens),
        "actives": sum(1 for b in biens if b.statut == Bien.Statut.DISPONIBLE and b.publie),
        "visites": DemandeVisite.objects.filter(bien__proprietaire=request.user, statut="attente").count(),
    }
    return render(request, "listings/mes_annonces.html", {"biens": biens, "totaux": totaux})


@login_required
def mes_favoris(request):
    ids = Favori.objects.filter(utilisateur=request.user).values_list("bien_id", flat=True)
    biens = biens_publics().filter(pk__in=ids)
    return render(request, "listings/favoris.html", {"biens": biens})


@login_required
@require_POST
def basculer_favori(request, ref):
    bien = get_object_or_404(Bien, reference=ref, publie=True)
    f, cree = Favori.objects.get_or_create(utilisateur=request.user, bien=bien)
    if not cree:
        f.delete()
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"favori": cree})
    return _retour(request, bien.get_absolute_url())


@require_POST
def signaler(request, ref):
    bien = get_object_or_404(Bien, reference=ref)
    form = SignalementForm(request.POST)
    if form.is_valid():
        s = form.save(commit=False)
        s.bien = bien
        s.auteur = request.user if request.user.is_authenticated else None
        s.save()
        messages.success(request, "Merci. Notre équipe vérifie cette annonce.")
    else:
        messages.error(request, "Choisissez un motif pour signaler l'annonce.")
    return redirect(bien)


def contact(request, ref, canal):
    bien = get_object_or_404(Bien.objects.select_related("ville", "quartier", "proprietaire"), reference=ref, publie=True)
    if request.user != bien.proprietaire:
        Bien.objects.filter(pk=bien.pk).update(contacts=F("contacts") + 1)
    if canal == "whatsapp":
        texte = (
            f"Bonjour, je suis intéressé(e) par votre annonce « {bien.objet} » à {bien.localisation_courte} "
            f"(réf. {bien.reference}) sur Congo Immo. Est-elle toujours disponible ?"
        )
        return HttpResponseRedirect(f"https://wa.me/{bien.proprietaire.numero_whatsapp}?text={quote(texte)}")
    return HttpResponse(status=204)


def affiche(request, ref):
    """Affiche A4 « À LOUER / À VENDRE » avec QR code, à imprimer et coller sur le bien."""
    bien = get_object_or_404(Bien.objects.select_related("ville", "quartier", "proprietaire"), reference=ref)
    url = request.build_absolute_uri(bien.get_absolute_url())
    qr = segno.make(url, error="m").svg_inline(scale=8, border=1, dark="#13201A", omitsize=True)
    return render(request, "listings/affiche.html", {"b": bien, "qr": qr, "url": url})


def profil_public(request, pk):
    agent = get_object_or_404(User, pk=pk, is_active=True)
    biens = biens_publics().filter(proprietaire=agent, statut=Bien.Statut.DISPONIBLE)
    return render(request, "listings/profil_public.html", {"agent": agent, "biens": biens})


def conseils(request):
    return render(request, "listings/conseils.html")
