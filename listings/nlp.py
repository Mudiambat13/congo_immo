"""Recherche en langage naturel, sans service externe : « maison 3 chambres Golf moins de 500$ »."""
import re
import unicodedata

from .models import Quartier, Ville
from .services import resumer_params


def _n(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


CATEGORIES = [
    ("parcelle", ("parcelle", "parcelles", "terrain", "terrains", "lopin")),
    ("concession", ("concession", "ferme", "champ", "hectare", "hectares")),
    ("appartement", ("appartement", "appartements", "appart")),
    ("studio", ("studio", "studios")),
    ("boutique", ("boutique", "magasin", "local commercial", "local", "commerce")),
    ("bureau", ("bureau", "bureaux")),
    ("entrepot", ("entrepot", "entrepots", "hangar", "depot")),
    ("maison", ("maison", "maisons", "villa", "villas", "duplex", "residence")),
]
LOCATION = ("louer", "location", "loyer", "locatif", "a louer")
VENTE = ("acheter", "achat", "vendre", "vente", "a vendre", "acquerir")


def _mots(texte, mots):
    return any(re.search(rf"(?<![a-z]){re.escape(m)}(?![a-z])", texte) for m in mots)


def _nombre(brut, suffixe=""):
    brut = re.sub(r"[.,](?=\d{3}(?!\d))", "", brut.strip()).replace(" ", "").replace(",", ".")
    try:
        v = float(brut)
    except ValueError:
        return None
    if suffixe == "k":
        v *= 1000
    return str(int(v)) if v == int(v) else str(v)


def analyser_recherche(texte):
    """Retourne (paramètres de filtre, liste lisible de ce qui a été compris)."""
    t = " " + _n(texte) + " "
    p = {}
    if _mots(t, LOCATION):
        p["type"] = "location"
    elif _mots(t, VENTE):
        p["type"] = "vente"
    for cat, mots in CATEGORIES:
        if _mots(t, mots):
            p["categorie"] = cat
            break
    m = re.search(r"(\d+)\s*(?:chambres?|ch\b|pieces?)", t)
    if m:
        p["chambres"] = m.group(1)

    villes = sorted(Ville.objects.all(), key=lambda v: -len(v.nom))
    ville = next((v for v in villes if re.search(rf"(?<![a-z]){re.escape(_n(v.nom))}(?![a-z])", t)), None)
    if ville:
        p["ville"] = str(ville.pk)
    qs = Quartier.objects.filter(ville=ville) if ville else Quartier.objects.all()
    for q in sorted(qs, key=lambda q: -len(q.nom)):
        if re.search(rf"(?<![a-z]){re.escape(_n(q.nom))}(?![a-z])", t):
            p["quartier"] = q.nom
            if not ville:
                p["ville"] = str(q.ville_id)
            break

    unite = r"(k|\$|usd|dollars?|fc|cdf|francs?)"
    entre = re.search(rf"entre\s+(\d[\d .,]*?)\s*(k)?\s+et\s+(\d[\d .,]*?)\s*{unite}?(?:\s|$)", t)
    maxi = re.search(rf"(?:moins de|max(?:imum)?|jusqu'?a|inferieur a|budget(?: de)?|<=?)\s*(\d[\d .,]*?)\s*{unite}?(?:\s|$)", t)
    seul = re.search(rf"(\d[\d .,]*?)\s*(\$|usd|dollars?|fc|cdf|francs?)(?:\s|$)", t)
    devise = None
    if entre:
        a, b = _nombre(entre.group(1), entre.group(2) or ""), _nombre(entre.group(3), entre.group(4) if entre.group(4) == "k" else "")
        if a and b:
            p["prix_min"], p["prix_max"] = sorted((a, b), key=float)
        devise = entre.group(4)
    elif maxi:
        suf = maxi.group(2) or ""
        v = _nombre(maxi.group(1), "k" if suf == "k" else "")
        if v:
            p["prix_max"] = v
        devise = suf
    elif seul:
        v = _nombre(seul.group(1))
        if v:
            p["prix_max"] = v
        devise = seul.group(2)
    if devise in ("fc", "cdf", "franc", "francs"):
        p["devise"] = "CDF"
    elif devise in ("$", "usd", "dollar", "dollars"):
        p["devise"] = "USD"

    from django.http import QueryDict
    qd = QueryDict(mutable=True)
    qd.update(p)
    return p, resumer_params(qd)
