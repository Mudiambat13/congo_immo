"""Alertes, notifications et résumés de recherche."""
from django.conf import settings
from django.core.mail import send_mail
from django.http import QueryDict
from django.urls import reverse

from .models import AlerteRecherche, Bien, Favori, Notification, Province, Quartier, Ville

CLES_ALERTE = ("type", "categorie", "province", "ville", "quartier", "devise", "prix_min", "prix_max", "chambres", "document", "verifie", "q")


def nettoyer_params(params):
    """Ne garde que les critères de recherche utiles pour une alerte."""
    return {k: params.get(k).strip() for k in CLES_ALERTE if params.get(k) and params.get(k).strip()}


def resumer_params(params):
    """Phrase lisible à partir des critères : « À louer, Maison, 3 chambres min., Lubumbashi, jusqu'à 500 USD »."""
    out = []
    if params.get("type") == "location":
        out.append("À louer")
    elif params.get("type") == "vente":
        out.append("À vendre")
    if params.get("categorie") in Bien.Categorie.values:
        out.append(Bien.Categorie(params["categorie"]).label)
    if params.get("chambres", "").isdigit():
        out.append(f"{params['chambres']} chambres min.")
    if params.get("ville", "").isdigit():
        nom = Ville.objects.filter(pk=int(params["ville"])).values_list("nom", flat=True).first()
        if nom:
            out.append(nom)
    elif params.get("province", "").isdigit():
        nom = Province.objects.filter(pk=int(params["province"])).values_list("nom", flat=True).first()
        if nom:
            out.append(nom)
    if params.get("quartier"):
        out.append(params["quartier"])
    unite = params.get("devise") or "USD"
    if params.get("prix_min") and params.get("prix_max"):
        out.append(f"{params['prix_min']} à {params['prix_max']} {unite}")
    elif params.get("prix_max"):
        out.append(f"jusqu'à {params['prix_max']} {unite}")
    elif params.get("prix_min"):
        out.append(f"dès {params['prix_min']} {unite}")
    if params.get("document") in Bien.Document.values:
        out.append(Bien.Document(params["document"]).label)
    if params.get("verifie") == "1":
        out.append("annonceurs vérifiés")
    if params.get("q"):
        out.append(f"« {params['q']} »")
    return out


def _email(user, sujet, corps):
    if getattr(settings, "ALERTES_EMAIL", False) and user.email:
        send_mail(sujet, corps, None, [user.email], fail_silently=True)


def notifier_alertes(bien):
    """À la publication d'un bien : prévient les personnes dont une recherche enregistrée correspond."""
    from .filtres import appliquer_filtres
    if not bien.publie or bien.statut != Bien.Statut.DISPONIBLE:
        return 0
    n = 0
    for a in AlerteRecherche.objects.filter(active=True).exclude(utilisateur_id=bien.proprietaire_id).select_related("utilisateur")[:3000]:
        if appliquer_filtres(Bien.objects.filter(pk=bien.pk), QueryDict(a.parametres)).exists():
            titre = f"Nouveau : {bien.objet} à {bien.localisation_courte}"
            Notification.objects.create(
                utilisateur=a.utilisateur, type=Notification.Type.ALERTE, titre=titre,
                message=f"{bien.prix_affiche}{' par mois' if bien.est_location else ''}. Correspond à votre alerte : {a.resume}", bien=bien,
            )
            _email(a.utilisateur, titre, f"{bien.prix_affiche}. Voir : /bien/{bien.reference}/")
            n += 1
    return n


def notifier_baisse_prix(bien, ancien_prix):
    n = 0
    for f in Favori.objects.filter(bien=bien).exclude(utilisateur_id=bien.proprietaire_id).select_related("utilisateur"):
        Notification.objects.create(
            utilisateur=f.utilisateur, type=Notification.Type.BAISSE, bien=bien,
            titre=f"Prix en baisse : {bien.objet}",
            message=f"Maintenant {bien.prix_affiche}, avant {bien.prix_avant_affiche}.",
        )
        n += 1
    return n


def notifier_visite(visite):
    b = visite.bien
    Notification.objects.create(
        utilisateur=b.proprietaire, type=Notification.Type.VISITE, bien=b, url=reverse("listings:visites"),
        titre=f"Demande de visite : {b.objet}",
        message=f"{visite.nom} souhaite visiter le {visite.date_souhaitee:%d/%m/%Y}, {visite.get_creneau_display().lower()}.",
    )
    _email(b.proprietaire, f"Demande de visite pour {b.objet}", f"{visite.nom} ({visite.telephone}) souhaite visiter le {visite.date_souhaitee:%d/%m/%Y}.")
