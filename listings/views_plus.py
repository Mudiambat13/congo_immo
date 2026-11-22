"""Fonctions « plus » : recherche en langage naturel, comparateur, visites, alertes, notifications, PWA."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .filtres import biens_publics
from .forms import VisiteForm
from .models import AlerteRecherche, Bien, DemandeVisite, Notification, Quartier, formater_prix
from .nlp import analyser_recherche
from .services import nettoyer_params, notifier_visite
from .views import _charger_bien, _retour, rendre_detail


# ---------- Recherche en une phrase ----------
def recherche_intelligente(request):
    texte = (request.GET.get("q") or "").strip()[:200]
    if not texte:
        return redirect("listings:liste")
    params, resume = analyser_recherche(texte)
    if params:
        messages.info(request, "Recherche comprise : " + ", ".join(resume) + ". Ajustez les filtres si besoin.")
        return redirect(f"{reverse('listings:liste')}?{urlencode(params)}")
    return redirect(f"{reverse('listings:liste')}?{urlencode({'q': texte})}")


# ---------- Visites ----------
def _trop_de_demandes(request, cle, maxi):
    return cache.get(f"lim:{cle}:{request.META.get('REMOTE_ADDR', '?')}", 0) >= maxi


def _compter(request, cle, secondes):
    k = f"lim:{cle}:{request.META.get('REMOTE_ADDR', '?')}"
    cache.set(k, cache.get(k, 0) + 1, secondes)


@require_POST
def demander_visite(request, ref):
    bien = get_object_or_404(Bien, reference=ref, publie=True, statut=Bien.Statut.DISPONIBLE)
    if _trop_de_demandes(request, "visite", 5):
        messages.error(request, "Trop de demandes en peu de temps. Réessayez dans une heure.")
        return redirect(bien)
    form = VisiteForm(request.POST)
    if form.is_valid():
        v = form.save(commit=False)
        v.bien = bien
        v.demandeur = request.user if request.user.is_authenticated else None
        v.save()
        _compter(request, "visite", 3600)
        notifier_visite(v)
        messages.success(request, "Demande envoyée. Le propriétaire vous répond par WhatsApp ou par téléphone.")
        return redirect(f"{bien.get_absolute_url()}#visite")
    return rendre_detail(request, _charger_bien(ref), form_visite=form)


@login_required
def visites_recues(request):
    visites = list(DemandeVisite.objects.filter(bien__proprietaire=request.user).select_related("bien__ville", "bien__quartier"))
    attente = [v for v in visites if v.statut == DemandeVisite.Statut.ATTENTE]
    traitees = [v for v in visites if v.statut != DemandeVisite.Statut.ATTENTE]
    return render(request, "listings/visites.html", {"attente": attente, "traitees": traitees})


@login_required
@require_POST
def statut_visite(request, pk):
    v = get_object_or_404(DemandeVisite.objects.select_related("bien"), pk=pk, bien__proprietaire=request.user)
    nouveau = request.POST.get("statut")
    if nouveau in DemandeVisite.Statut.values:
        v.statut = nouveau
        v.save(update_fields=["statut"])
        if v.demandeur_id and nouveau != DemandeVisite.Statut.ATTENTE:
            mot = "confirmée" if nouveau == DemandeVisite.Statut.CONFIRMEE else "refusée"
            Notification.objects.create(
                utilisateur=v.demandeur, type=Notification.Type.VISITE, bien=v.bien,
                titre=f"Visite {mot} : {v.bien.objet}", message=f"Pour le {v.date_souhaitee:%d/%m/%Y}, {v.get_creneau_display().lower()}.",
            )
        messages.success(request, "Réponse enregistrée. Prévenez la personne par WhatsApp avec le bouton prévu.")
    return redirect("listings:visites")


# ---------- Comparateur ----------
@require_POST
def basculer_comparaison(request, ref):
    get_object_or_404(Bien, reference=ref, publie=True)
    liste = list(request.session.get("comparaison", []))
    if ref in liste:
        liste.remove(ref)
        actif = False
    elif len(liste) >= 3:
        if request.headers.get("x-requested-with") == "fetch":
            return JsonResponse({"erreur": "Vous pouvez comparer 3 biens au maximum.", "n": len(liste), "refs": liste}, status=409)
        messages.error(request, "Vous pouvez comparer 3 biens au maximum.")
        return redirect("listings:comparer")
    else:
        liste.append(ref)
        actif = True
    request.session["comparaison"] = liste
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"actif": actif, "n": len(liste), "refs": liste})
    return redirect("listings:comparer")


def comparer(request):
    refs = request.session.get("comparaison", [])
    par_ref = {b.reference: b for b in biens_publics().prefetch_related("equipements").filter(reference__in=refs)}
    biens = [par_ref[r] for r in refs if r in par_ref]
    meilleur = None
    if len(biens) >= 2 and len({(b.type_annonce, b.devise) for b in biens}) == 1:
        meilleur = min(biens, key=lambda b: b.prix).reference
    equipements = sorted({e.nom for b in biens for e in b.equipements.all()})
    lignes = [{"nom": n, "presents": [any(e.nom == n for e in b.equipements.all()) for b in biens]} for n in equipements]
    return render(request, "listings/comparer.html", {"biens": biens, "meilleur": meilleur, "lignes_equipements": lignes})


@require_POST
def vider_comparaison(request):
    request.session["comparaison"] = []
    return redirect("listings:comparer")


# ---------- Alertes ----------
@login_required
@require_POST
def sauvegarder_recherche(request):
    params = nettoyer_params(QueryDict(request.POST.get("parametres", "")))
    if not params:
        messages.error(request, "Choisissez au moins un critère (type, ville, budget...) avant d'enregistrer une alerte.")
        return _retour(request, "listings:liste")
    if request.user.alertes.count() >= 10:
        messages.error(request, "Vous avez déjà 10 alertes. Supprimez-en une pour en créer une nouvelle.")
        return redirect("listings:alertes")
    _, cree = AlerteRecherche.objects.get_or_create(utilisateur=request.user, parametres=urlencode(params))
    messages.success(request, "Alerte enregistrée. Vous serez prévenu dès qu'une annonce correspond." if cree else "Cette alerte existe déjà.")
    return redirect("listings:alertes")


@login_required
def mes_alertes(request):
    return render(request, "listings/alertes.html", {"alertes": request.user.alertes.all()})


@login_required
@require_POST
def action_alerte(request, pk):
    a = get_object_or_404(AlerteRecherche, pk=pk, utilisateur=request.user)
    if request.POST.get("action") == "supprimer":
        a.delete()
        messages.success(request, "Alerte supprimée.")
    else:
        a.active = not a.active
        a.save(update_fields=["active"])
    return redirect("listings:alertes")


# ---------- Notifications ----------
@login_required
def notifications(request):
    liste = list(request.user.notifications.select_related("bien")[:60])
    non_lues = [n.pk for n in liste if not n.lu]
    reponse = render(request, "listings/notifications.html", {"notifications": liste})
    if non_lues:
        Notification.objects.filter(pk__in=non_lues).update(lu=True)
    return reponse


# ---------- Prix du marché (aide à la saisie) ----------
def api_marche(request):
    g = request.GET
    if g.get("type") not in ("location", "vente") or g.get("categorie") not in Bien.Categorie.values or not g.get("ville", "").isdigit():
        return JsonResponse({"disponible": False})
    devise = g.get("devise") if g.get("devise") in Bien.Devise.values else "USD"
    ville = int(g["ville"])
    nom = g.get("quartier", "").strip()
    qid = Quartier.objects.filter(ville_id=ville, nom__iexact=nom).values_list("id", flat=True).first() if nom else None
    st = Bien.stats_marche(g["type"], g["categorie"], devise, ville, qid)
    if not st:
        return JsonResponse({"disponible": False})
    return JsonResponse({
        "disponible": True, "portee": st["portee"], "n": st["n"], "moy": st["moy"],
        "moyenne": formater_prix(st["moy"], devise), "mini": formater_prix(st["mini"], devise), "maxi": formater_prix(st["maxi"], devise),
    })


# ---------- Application installable (PWA) et robots ----------
def manifest(request):
    data = {
        "name": "Congo Immo", "short_name": "Congo Immo", "lang": "fr", "dir": "ltr",
        "description": "Maisons, parcelles et locaux à louer ou à vendre partout en RDC.",
        "start_url": "/?source=pwa", "scope": "/", "display": "standalone", "orientation": "portrait",
        "background_color": "#0E3B2C", "theme_color": "#0E3B2C",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Publier un bien", "url": reverse("listings:creer")},
            {"name": "Biens à louer", "url": reverse("listings:louer")},
            {"name": "Carte des biens", "url": reverse("listings:carte")},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


def service_worker(request):
    r = render(request, "sw.js", content_type="application/javascript")
    r["Cache-Control"] = "no-cache"
    return r


def hors_ligne(request):
    return render(request, "listings/hors_ligne.html")


def robots(request):
    corps = (
        "User-agent: *\nDisallow: /admin/\nDisallow: /compte/\nDisallow: /api/\nDisallow: /alertes/\nDisallow: /notifications/\nDisallow: /visites/\n"
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml\n"
    )
    return HttpResponse(corps, content_type="text/plain; charset=utf-8")
