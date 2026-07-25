"""Cálculos estadísticos sencillos usados en el dashboard (sin dependencias
pesadas como numpy/pandas, para mantener el proyecto ligero en Vercel)."""

from collections import defaultdict


def crosstab(registros, campo, categorias_resultado):
    """Genera una tabla cruzada {valor_de_campo: {categoria_resultado: conteo}}
    a partir de una lista de dicts con las claves 'resultado_kit_ic' y `campo`.
    """
    tabla = defaultdict(lambda: {c: 0 for c in categorias_resultado})
    for r in registros:
        valor = r.get(campo)
        resultado = r.get("resultado_kit_ic")
        if valor is None or resultado not in categorias_resultado:
            continue
        tabla[valor][resultado] += 1
    return dict(tabla)
