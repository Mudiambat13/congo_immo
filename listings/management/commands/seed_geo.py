from django.core.management.base import BaseCommand

from listings.models import Equipement, Province, Quartier, Ville

PROVINCES = [
    "Bas-Uele", "Équateur", "Haut-Katanga", "Haut-Lomami", "Haut-Uele", "Ituri", "Kasaï", "Kasaï-Central",
    "Kasaï-Oriental", "Kinshasa", "Kongo-Central", "Kwango", "Kwilu", "Lomami", "Lualaba", "Mai-Ndombe",
    "Maniema", "Mongala", "Nord-Kivu", "Nord-Ubangi", "Sankuru", "Sud-Kivu", "Sud-Ubangi", "Tanganyika",
    "Tshopo", "Tshuapa",
]

# (province, ville, code, latitude, longitude)
VILLES = [
    ("Kinshasa", "Kinshasa", "KIN", -4.3250, 15.3222),
    ("Haut-Katanga", "Lubumbashi", "LSH", -11.6609, 27.4794),
    ("Haut-Katanga", "Likasi", "LIK", -10.9833, 26.7333),
    ("Haut-Katanga", "Kipushi", "KIP", -11.7600, 27.2400),
    ("Haut-Katanga", "Kasumbalesa", "KSB", -12.2600, 27.8100),
    ("Haut-Katanga", "Sakania", "SAK", -12.7400, 28.5700),
    ("Lualaba", "Kolwezi", "KWZ", -10.7167, 25.4667),
    ("Lualaba", "Fungurume", "FGR", -10.6200, 26.3200),
    ("Kasaï-Oriental", "Mbuji-Mayi", "MBM", -6.1360, 23.5897),
    ("Kasaï-Central", "Kananga", "KGA", -5.8970, 22.4170),
    ("Kasaï", "Tshikapa", "TSH", -6.4167, 20.8000),
    ("Kwilu", "Kikwit", "KKW", -5.0410, 18.8160),
    ("Kwilu", "Bandundu", "BDD", -3.3167, 17.3833),
    ("Kongo-Central", "Matadi", "MTD", -5.8167, 13.4500),
    ("Kongo-Central", "Boma", "BMA", -5.8500, 13.0500),
    ("Kongo-Central", "Mbanza-Ngungu", "MBN", -5.2500, 14.8667),
    ("Nord-Kivu", "Goma", "GOM", -1.6792, 29.2228),
    ("Nord-Kivu", "Butembo", "BUT", 0.1167, 29.2833),
    ("Nord-Kivu", "Beni", "BEN", 0.4910, 29.4730),
    ("Sud-Kivu", "Bukavu", "BKV", -2.5083, 28.8608),
    ("Sud-Kivu", "Uvira", "UVI", -3.4000, 29.1500),
    ("Tshopo", "Kisangani", "KIS", 0.5153, 25.1910),
    ("Ituri", "Bunia", "BUN", 1.5667, 30.2500),
    ("Tanganyika", "Kalemie", "KLM", -5.9475, 29.1947),
    ("Maniema", "Kindu", "KDU", -2.9500, 25.9167),
    ("Équateur", "Mbandaka", "MBK", 0.0487, 18.2603),
    ("Sud-Ubangi", "Gemena", "GEM", 3.2500, 19.7667),
    ("Mongala", "Lisala", "LIS", 2.1500, 21.5167),
    ("Haut-Uele", "Isiro", "ISR", 2.7740, 27.6160),
    ("Bas-Uele", "Buta", "BTA", 2.8000, 24.7333),
    ("Nord-Ubangi", "Gbadolite", "GBD", 4.2833, 21.0000),
    ("Kwango", "Kenge", "KEN", -4.8500, 17.0333),
    ("Lomami", "Kabinda", "KAB", -6.1333, 24.4833),
    ("Haut-Lomami", "Kamina", "KAM", -8.7386, 25.0000),
    ("Sankuru", "Lusambo", "LUS", -4.9667, 23.4500),
    ("Mai-Ndombe", "Inongo", "INO", -1.9500, 18.2667),
    ("Tshuapa", "Boende", "BOE", -0.2167, 20.8667),
]

EQUIPEMENTS = [
    "Eau courante (REGIDESO)", "Forage ou puits", "Électricité (SNEL)", "Panneau solaire", "Groupe électrogène",
    "Citerne", "Clôture / mur", "Parking", "Gardien", "Meublé", "Carrelage", "Plafond", "Internet / fibre",
    "Cuisine interne", "Cour intérieure", "Terrasse / véranda", "Climatisation",
]

QUARTIERS = {
    "Lubumbashi": ["Bel-Air", "Golf", "Makomeno", "Kenya", "Ruashi", "Kamalondo", "Kampemba", "Katuba", "Industriel", "Lido"],
    "Kinshasa": ["Gombe", "Limete", "Ngaliema", "Bandalungwa", "Kintambo", "Lemba", "Ma Campagne", "Binza"],
    "Goma": ["Himbi", "Les Volcans", "Katindo", "Mabanga", "Ndosho"],
    "Kolwezi": ["Mutoshi", "Dilala", "Musonoie", "Manika"],
}


class Command(BaseCommand):
    help = "Charge les 26 provinces, les principales villes, des quartiers courants et les équipements."

    def handle(self, *args, **opts):
        provinces = {nom: Province.objects.get_or_create(nom=nom)[0] for nom in PROVINCES}
        for prov, nom, code, lat, lng in VILLES:
            Ville.objects.update_or_create(code=code, defaults={"province": provinces[prov], "nom": nom, "latitude": lat, "longitude": lng})
        for nom in EQUIPEMENTS:
            Equipement.objects.get_or_create(nom=nom)
        for ville, noms in QUARTIERS.items():
            v = Ville.objects.get(nom=ville)
            for n in noms:
                Quartier.objects.get_or_create(ville=v, nom=n)
        self.stdout.write(self.style.SUCCESS(f"{Province.objects.count()} provinces, {Ville.objects.count()} villes, {Equipement.objects.count()} équipements."))
