import random
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from accounts.models import User
from listings.models import Bien, Equipement, PhotoBien, Quartier, Ville

MURS = ["#E8D9B5", "#C9D6C3", "#D8C3A5", "#B9CBD9", "#EBC8B2", "#CFCFC4"]
TOITS = ["#7A2E2E", "#2F4F4F", "#44475A", "#5B3A29", "#34495E"]


def image_factice(seed, vente=False):
    rnd = random.Random(seed)
    w, h = 1200, 800
    img = Image.new("RGB", (w, h), "#CFE3F2")
    d = ImageDraw.Draw(img)
    for y in range(h // 2):
        t = y / (h // 2)
        d.line([(0, y), (w, y)], fill=(int(207 + 30 * t), int(227 + 18 * t), int(242 + 5 * t)))
    d.rectangle([0, int(h * 0.62), w, h], fill=rnd.choice(["#B08A57", "#A67C52", "#8F9A5B"]))
    if vente:
        for i in range(8):
            x = 80 + i * 150
            d.line([(x, int(h * 0.62)), (x + 40, int(h * 0.9))], fill="#6B5B3E", width=3)
        d.rectangle([w * 0.2, h * 0.42, w * 0.22, h * 0.7], fill="#6B5B3E")
        d.rectangle([w * 0.2, h * 0.42, w * 0.42, h * 0.52], fill="#F4B400")
        return img
    mur = rnd.choice(MURS)
    toit = rnd.choice(TOITS)
    x0, x1, y0, y1 = w * 0.18, w * 0.82, h * 0.34, h * 0.78
    d.rectangle([x0, y0, x1, y1], fill=mur)
    d.polygon([(x0 - 40, y0), (w / 2, h * 0.14), (x1 + 40, y0)], fill=toit)
    d.rectangle([w * 0.46, h * 0.52, w * 0.54, y1], fill="#4A3427")
    for fx in (0.26, 0.64):
        d.rectangle([w * fx, h * 0.46, w * (fx + 0.1), h * 0.6], fill="#8FB8D6", outline="#F4F1EA", width=6)
    d.rectangle([x0 - 20, y1, x1 + 20, y1 + 14], fill="#8C8C84")
    return img


def en_jpeg(img):
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue(), name="demo.jpg")


DEMOS = [
    ("location", "maison", "Maison locative", "2 chambres, salon, sanitaire interne, cour carrelée, quartier calme et bien desservi.", "Lubumbashi", "Bel-Air", "Avenue Tulipier n°2", -11.6702, 27.4905, "USD", 350, 3, 1, 2, 1, 1, ["Eau courante (REGIDESO)", "Électricité (SNEL)", "Clôture / mur", "Carrelage"]),
    ("location", "appartement", "Appartement meublé", "3 chambres, grand salon, cuisine équipée, gardien 24h/24, parking pour deux véhicules.", "Lubumbashi", "Golf", "Avenue Kasai n°14", -11.6455, 27.4880, "USD", 900, 3, 0, 3, 1, 2, ["Meublé", "Gardien", "Parking", "Groupe électrogène", "Climatisation"]),
    ("location", "studio", "Studio indépendant", "Chambre-salon avec douche interne, entrée indépendante, idéal pour une personne seule.", "Lubumbashi", "Kenya", "Avenue Mbuji-Mayi n°7", -11.6890, 27.5120, "USD", 120, 2, 1, 1, 0, 1, ["Eau courante (REGIDESO)", "Électricité (SNEL)"]),
    ("location", "maison", "Villa familiale", "4 chambres dont 2 avec douche, salon double, jardin, forage et panneaux solaires.", "Kinshasa", "Ma Campagne", "Avenue Mama Yemo n°21", -4.3560, 15.2630, "USD", 1500, 3, 1, 4, 2, 3, ["Forage ou puits", "Panneau solaire", "Clôture / mur", "Parking", "Gardien"]),
    ("location", "boutique", "Local commercial sur avenue", "Local de 40 m² face à l'avenue principale, vitrine, arrière-boutique et sanitaire.", "Goma", "Himbi", "Avenue de la Paix n°5", -1.6770, 29.2300, "USD", 400, 2, 0, None, None, 1, ["Électricité (SNEL)", "Carrelage"]),
    ("location", "maison", "Maison 3 chambres", "Maison simple et propre, salon, 3 chambres, cour intérieure pour enfants.", "Kolwezi", "Mutoshi", "Avenue des Mines n°3", -10.7120, 25.4700, "USD", 280, 2, 1, 3, 1, 1, ["Cour intérieure", "Eau courante (REGIDESO)"]),
    ("vente", "parcelle", "Parcelle 15 × 25 m", "Terrain plat, déjà borné, accès par route carrossable, voisinage résidentiel.", "Lubumbashi", "Ruashi", "Route Kasumbalesa, après le marché", -11.6180, 27.5560, "USD", 18000, None, None, None, None, None, [], 375, "certificat"),
    ("vente", "parcelle", "Parcelle d'angle", "Parcelle d'angle sur deux avenues, idéale pour construire une maison avec boutique.", "Lubumbashi", "Makomeno", "Avenue Likasi n°40", -11.7050, 27.4600, "USD", 25000, None, None, None, None, None, [], 450, "contrat_location"),
    ("vente", "maison", "Maison 5 pièces avec clôture", "Maison de 3 chambres, salon, annexe de 2 pièces, mur de clôture et portail métallique.", "Kinshasa", "Limete", "11e rue Limete n°118", -4.3470, 15.3340, "USD", 95000, None, None, 4, 1, 2, ["Clôture / mur", "Parking", "Carrelage"], 400, "certificat"),
    ("vente", "concession", "Concession de 2 hectares", "Terrain agricole avec point d'eau, clôturé à moitié, accès toute l'année.", "Kolwezi", "Dilala", "Route de Fungurume, km 12", -10.7500, 25.5200, "USD", 40000, None, None, None, None, None, [], 20000, "attestation"),
]


class Command(BaseCommand):
    help = "Crée un compte démo et des annonces d'exemple (développement uniquement)."

    def handle(self, *args, **opts):
        call_command("seed_geo", verbosity=0)
        user, cree = User.objects.get_or_create(
            email="demo@congoimmo.cd",
            defaults={"username": "demo", "first_name": "Alice", "last_name": "Démo", "telephone": "0812345678", "whatsapp": "0812345678", "role": "agence", "est_verifie": True, "bio": "Compte de démonstration."},
        )
        if cree:
            user.set_password("demo1234")
            user.save()
        n = 0
        for i, row in enumerate(DEMOS):
            (typ, cat, objet, desc, ville, quartier, adresse, lat, lng, devise, prix,
             garantie, avance, chambres, salons, sanitaires, equip) = row[:17]
            sup, doc = (row[17], row[18]) if len(row) > 17 else (None, "")
            if Bien.objects.filter(proprietaire=user, objet=objet, adresse=adresse).exists():
                continue
            v = Ville.objects.get(nom=ville)
            q, _ = Quartier.objects.get_or_create(ville=v, nom=quartier)
            b = Bien.objects.create(
                proprietaire=user, type_annonce=typ, categorie=cat, objet=objet, description=desc, ville=v, quartier=q,
                adresse=adresse, latitude=Decimal(str(lat)), longitude=Decimal(str(lng)), devise=devise, prix=Decimal(prix),
                garantie_mois=garantie if typ == "location" else None, avance_mois=avance if typ == "location" else None,
                modalites="Loyer payable le 5 de chaque mois. Bail d'un an renouvelable. Visite sur rendez-vous." if typ == "location" else "",
                chambres=chambres, salons=salons, sanitaires=sanitaires, superficie=sup, type_document=doc or "",
                est_verifie=(i % 3 == 0),
            )
            b.equipements.set(Equipement.objects.filter(nom__in=equip))
            for k in range(3 if typ == "vente" else 4):
                PhotoBien.objects.create(bien=b, image=en_jpeg(image_factice(i * 10 + k, vente=(cat in ("parcelle", "concession")))), ordre=k)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"{n} annonces de démonstration créées. Connexion : demo@congoimmo.cd / demo1234"))
