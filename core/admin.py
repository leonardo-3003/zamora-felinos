from django.contrib import admin

from .models import RegistroGato, Propietario


@admin.register(Propietario)
class PropietarioAdmin(admin.ModelAdmin):
    list_display = (
        "cedula", "nombre_completo", "barrio", "telefono", "correo", "creado_en",
    )
    search_fields = ("nombres", "apellidos", "cedula", "telefono", "correo", "barrio")
    list_filter = ("barrio", "creado_en",)
    readonly_fields = ("creado_en",)


@admin.register(RegistroGato)
class RegistroGatoAdmin(admin.ModelAdmin):
    list_display = (
        "id_gato", "nombre", "sexo", "edad_meses",
        "propietario", "resultado_kit_ic", "fecha_muestreo",
    )
    list_filter = ("resultado_kit_ic", "sexo", "estado_salud", "antecedente_transfusion", "tiene_carnet_vacunacion", "tipo_raza", "propietario__barrio")
    search_fields = ("id_gato", "nombre", "propietario__nombres", "propietario__apellidos", "propietario__cedula", "propietario__barrio")
    readonly_fields = ("id_gato", "fecha_muestreo", "creado_en")
