import io
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User
from accounts.utils import normaliser_telephone
from listings.models import Bien, PhotoBien, Ville


def png(nom="a.png", taille=(900, 600)):
    buf = io.BytesIO()
    Image.new("RGB", taille, "#c0a060").save(buf, "PNG")
    return SimpleUploadedFile(nom, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="congoimmo-test-"))
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_geo", verbosity=0)
        cls.user = User.objects.create_user(username="u1", email="a@b.cd", telephone="0812345678", password="motdepasse-solide-9", first_name="Alice")
        cls.autre = User.objects.create_user(username="u2", email="c@d.cd", telephone="0899999999", password="motdepasse-solide-9")
        cls.lubumbashi = Ville.objects.get(nom="Lubumbashi")

    def donnees_location(self, **extra):
        d = {
            "type_annonce": "location", "categorie": "maison", "objet": "Maison locative",
            "description": "2 chambres, salon, sanitaire", "ville": self.lubumbashi.pk, "quartier_nom": "bel-air",
            "adresse": "Avenue Tulipier n°2", "devise": "USD", "prix": "350", "garantie_mois": "3", "avance_mois": "1",
            "modalites": "Loyer payable le 5", "chambres": "2", "salons": "1", "sanitaires": "1",
        }
        d.update(extra)
        return d

    def creer_bien(self, **kw):
        defauts = dict(proprietaire=self.user, type_annonce="location", categorie="maison", objet="Maison test", description="d",
                       ville=self.lubumbashi, adresse="Av. Test 1", prix=Decimal("300"), garantie_mois=2)
        defauts.update(kw)
        b = Bien.objects.create(**defauts)
        PhotoBien.objects.create(bien=b, image=png())
        return b


class TestTelephone(TestCase):
    def test_normalisation(self):
        for entree in ("0812345678", "+243 81 234 5678", "243812345678", "812345678", "00243812345678"):
            self.assertEqual(normaliser_telephone(entree), "243812345678")


class TestPages(Base):
    def test_pages_publiques(self):
        b = self.creer_bien()
        for nom, args in [("listings:accueil", []), ("listings:liste", []), ("listings:louer", []), ("listings:acheter", []),
                          ("listings:carte", []), ("listings:conseils", []), ("accounts:connexion", []), ("accounts:inscription", []),
                          ("listings:detail", [b.reference]), ("listings:affiche", [b.reference]), ("listings:profil_public", [self.user.pk]),
                          ("listings:geojson", []), ("listings:api_quartiers", [])]:
            r = self.client.get(reverse(nom, args=args))
            self.assertEqual(r.status_code, 200, nom)

    def test_reference_generee(self):
        b = self.creer_bien()
        self.assertRegex(b.reference, r"^CI-LSH-\d{5}$")

    def test_photo_compressee_avec_miniature(self):
        b = self.creer_bien()
        p = b.photos.first()
        self.assertTrue(p.miniature)
        self.assertLessEqual(Image.open(p.miniature).width, 640)

    def test_pages_privees_redirigent(self):
        for nom in ("listings:creer", "listings:mes_annonces", "listings:favoris", "accounts:profil"):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 302)

    def test_filtres(self):
        self.creer_bien(prix=Decimal("100"), objet="Petit studio")
        self.creer_bien(prix=Decimal("900"), objet="Grande villa")
        r = self.client.get(reverse("listings:liste"), {"prix_max": "500"})
        self.assertContains(r, "Petit studio")
        self.assertNotContains(r, "Grande villa")


class TestPublication(Base):
    def setUp(self):
        self.client.force_login(self.user)

    def test_formulaire_s_affiche(self):
        for url in (reverse("listings:creer"), reverse("listings:creer") + "?type=vente"):
            r = self.client.get(url)
            self.assertContains(r, "carte-formulaire")
            self.assertContains(r, 'data-province="')
        b = self.creer_bien()
        self.assertContains(self.client.get(reverse("listings:modifier", args=[b.reference])), "Photos actuelles")
        self.assertContains(self.client.get(reverse("listings:mes_annonces")), b.reference)
        self.assertEqual(self.client.get(reverse("listings:supprimer", args=[b.reference])).status_code, 200)

    def test_publier_location(self):
        r = self.client.post(reverse("listings:creer"), {**self.donnees_location(), "photos_nouvelles": [png("1.png"), png("2.png")]})
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        b = Bien.objects.get()
        self.assertEqual(b.quartier.nom, "Bel-Air")  # réutilise le quartier existant, sans doublon
        self.assertEqual(b.photos.count(), 2)
        self.assertEqual(b.proprietaire, self.user)
        self.assertEqual(b.entree_total.replace("\u202f", "").replace("\u00a0", " "), "1400 $")

    def test_quartier_existant_reutilise(self):
        self.client.post(reverse("listings:creer"), {**self.donnees_location(quartier_nom="Bel-Air"), "photos_nouvelles": [png()]})
        self.assertEqual(Bien.objects.get().quartier.nom, "Bel-Air")

    def test_vente_exige_gps_superficie_document(self):
        d = self.donnees_location(type_annonce="vente", categorie="parcelle", prix="20000")
        r = self.client.post(reverse("listings:creer"), {**d, "photos_nouvelles": [png()]})
        self.assertEqual(r.status_code, 200)
        e = r.context["form"].errors
        self.assertIn("superficie", e)
        self.assertIn("type_document", e)
        self.assertIn("latitude", e)

    def test_publier_vente_complete(self):
        d = self.donnees_location(type_annonce="vente", categorie="parcelle", prix="20000", superficie="375",
                                  type_document="certificat", latitude="-11.670200", longitude="27.490500", chambres="")
        r = self.client.post(reverse("listings:creer"), {**d, "photos_nouvelles": [png()]})
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.status_code == 200 else "")
        b = Bien.objects.get()
        self.assertEqual(b.type_document, "certificat")
        self.assertIsNone(b.garantie_mois)
        self.assertTrue(b.prix_m2)

    def test_gps_hors_rdc_refuse(self):
        d = self.donnees_location(latitude="48.85", longitude="2.35")
        r = self.client.post(reverse("listings:creer"), {**d, "photos_nouvelles": [png()]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("latitude", r.context["form"].errors)

    def test_maximum_6_photos(self):
        r = self.client.post(reverse("listings:creer"), {**self.donnees_location(), "photos_nouvelles": [png(f"{i}.png") for i in range(7)]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("photos_nouvelles", r.context["form"].errors)
        self.assertEqual(Bien.objects.count(), 0)

    def test_au_moins_une_photo(self):
        r = self.client.post(reverse("listings:creer"), self.donnees_location())
        self.assertEqual(r.status_code, 200)
        self.assertIn("photos_nouvelles", r.context["form"].errors)

    def test_fichier_non_image_refuse(self):
        faux = SimpleUploadedFile("x.png", b"pas une image", content_type="image/png")
        r = self.client.post(reverse("listings:creer"), {**self.donnees_location(), "photos_nouvelles": [faux]})
        self.assertEqual(r.status_code, 200)

    def test_modifier_et_retirer_photo(self):
        b = self.creer_bien()
        ancienne = b.photos.first()
        r = self.client.post(reverse("listings:modifier", args=[b.reference]), {
            **self.donnees_location(objet="Maison rénovée"), "photos_nouvelles": [png("n.png")], "photos_a_supprimer": [ancienne.pk],
        })
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.status_code == 200 else "")
        b.refresh_from_db()
        self.assertEqual(b.objet, "Maison rénovée")
        self.assertEqual(b.photos.count(), 1)
        self.assertNotEqual(b.photos.first().pk, ancienne.pk)

    def test_pas_de_modification_par_un_autre(self):
        b = self.creer_bien()
        self.client.force_login(self.autre)
        self.assertEqual(self.client.get(reverse("listings:modifier", args=[b.reference])).status_code, 404)
        self.assertEqual(self.client.post(reverse("listings:statut", args=[b.reference]), {"statut": "conclu"}).status_code, 404)


class TestInteractions(Base):
    def test_statut_conclu_masque_des_recherches(self):
        b = self.creer_bien(objet="Maison louée")
        self.client.force_login(self.user)
        self.client.post(reverse("listings:statut", args=[b.reference]), {"statut": "conclu"})
        self.assertNotContains(self.client.get(reverse("listings:liste")), "Maison louée")
        self.assertContains(self.client.get(b.get_absolute_url()), "déjà loué")

    def test_annonce_masquee_introuvable(self):
        b = self.creer_bien(publie=False)
        self.assertEqual(self.client.get(b.get_absolute_url()).status_code, 404)

    def test_favori_bascule(self):
        b = self.creer_bien()
        self.client.force_login(self.autre)
        url = reverse("listings:favori", args=[b.reference])
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(r.json()["favori"])
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch")
        self.assertFalse(r.json()["favori"])

    def test_contact_whatsapp_compte_et_redirige(self):
        b = self.creer_bien()
        r = self.client.get(reverse("listings:contact", args=[b.reference, "whatsapp"]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("https://wa.me/243812345678?text="))
        b.refresh_from_db()
        self.assertEqual(b.contacts, 1)

    def test_vues_comptees_une_fois_par_session(self):
        b = self.creer_bien()
        self.client.get(b.get_absolute_url())
        self.client.get(b.get_absolute_url())
        b.refresh_from_db()
        self.assertEqual(b.vues, 1)

    def test_signalement(self):
        b = self.creer_bien()
        self.client.post(reverse("listings:signaler", args=[b.reference]), {"motif": "arnaque", "message": "suspect"})
        self.assertEqual(b.signalements.count(), 1)

    def test_comparaison_marche(self):
        for p in (200, 300, 400):
            self.creer_bien(prix=Decimal(p))
        b = self.creer_bien(prix=Decimal("600"))
        m = b.statistiques_marche()
        self.assertEqual(m["n"], 3)
        self.assertGreater(m["ecart"], 5)

    def test_xss_titre_echappe(self):
        b = self.creer_bien(objet="<script>alert(1)</script>")
        self.assertNotContains(self.client.get(b.get_absolute_url()), "<script>alert(1)</script>")


class TestComptes(Base):
    def test_inscription_puis_connexion_par_telephone(self):
        r = self.client.post(reverse("accounts:inscription"), {
            "first_name": "Jean", "last_name": "Mukendi", "telephone": "+243 99 123 4567", "whatsapp": "", "email": "jean@exemple.cd",
            "role": "particulier", "password1": "un-mot-de-passe-9X", "password2": "un-mot-de-passe-9X",
        })
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.status_code == 200 else "")
        self.client.logout()
        self.assertTrue(self.client.login(username="0991234567", password="un-mot-de-passe-9X"))
        self.client.logout()
        self.assertTrue(self.client.login(username="JEAN@exemple.cd", password="un-mot-de-passe-9X"))

    def test_telephone_en_double_refuse(self):
        r = self.client.post(reverse("accounts:inscription"), {
            "first_name": "X", "last_name": "Y", "telephone": "0812345678", "email": "nouveau@exemple.cd", "role": "particulier",
            "password1": "un-mot-de-passe-9X", "password2": "un-mot-de-passe-9X",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("telephone", r.context["form"].errors)
