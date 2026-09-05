from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Permite acceder a dictionary[key] desde el template (ej. {{ d|get_item:key }})."""
    if not dictionary:
        return None
    return dictionary.get(key)


@register.filter
def max_value(dictionary):
    """Devuelve el mayor valor de un dict (usado para escalar mini-barras en las
    tablas cruzadas: cada celda se dibuja en proporción al máximo de su fila)."""
    if not dictionary:
        return 0
    valores = dictionary.values()
    return max(valores) if valores else 0
