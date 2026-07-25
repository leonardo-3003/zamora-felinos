from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Permite acceder a dictionary[key] desde el template (ej. {{ d|get_item:key }})."""
    if not dictionary:
        return None
    return dictionary.get(key)
