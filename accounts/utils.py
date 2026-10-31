import re


def normaliser_telephone(valeur: str) -> str:
    """Retourne le numéro au format international sans '+', ex. 243812345678.

    Accepte 0812345678, +243 81 234 5678, 243812345678, 812345678.
    """
    chiffres = re.sub(r"\D", "", valeur or "")
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    if chiffres.startswith("243"):
        return chiffres
    if chiffres.startswith("0") and len(chiffres) == 10:
        return "243" + chiffres[1:]
    if len(chiffres) == 9:
        return "243" + chiffres
    return chiffres


def formater_telephone(numero: str) -> str:
    n = normaliser_telephone(numero)
    if n.startswith("243") and len(n) == 12:
        return f"+243 {n[3:5]} {n[5:8]} {n[8:]}"
    return f"+{n}" if n else ""
