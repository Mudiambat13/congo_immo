from django import template

from accounts.utils import formater_telephone

register = template.Library()


@register.filter
def telephone(valeur):
    return formater_telephone(valeur)


@register.simple_tag(takes_context=True)
def garder_params(context, **remplacements):
    """Reconstruit la query string courante en remplaçant/supprimant certains paramètres."""
    q = context["request"].GET.copy()
    for cle, val in remplacements.items():
        if val in (None, ""):
            q.pop(cle, None)
        else:
            q[cle] = val
    return q.urlencode()


@register.filter
def pluriel(n, mot):
    n = n or 0
    return f"{n} {mot}{'s' if n > 1 else ''}"
