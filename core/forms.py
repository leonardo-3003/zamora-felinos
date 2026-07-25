from django import forms
from .models import RegistroGato, Propietario


class PropietarioForm(forms.ModelForm):
    """Formulario para capturar datos del propietario."""
    class Meta:
        model = Propietario
        fields = ["nombres", "apellidos", "cedula", "telefono", "correo", "barrio", "latitud", "longitud"]
        widgets = {
            "barrio": forms.Select(attrs={"id": "id_barrio"}),
            "latitud": forms.HiddenInput(),
            "longitud": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ["latitud", "longitud"]:
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (existing + " form-control").strip()

        # Agregar clase is-invalid a campos con errores
        if self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    existing = self.fields[field_name].widget.attrs.get("class", "")
                    self.fields[field_name].widget.attrs["class"] = (existing + " is-invalid").strip()


class RegistroGatoForm(forms.ModelForm):
    # Campos de vacunación como checkboxes múltiples
    vacunas_seleccionadas = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[(v, v) for v in RegistroGato.VACUNAS_DISPONIBLES],
        label="Vacunas aplicadas"
    )

    class Meta:
        model = RegistroGato
        exclude = ["registrado_por", "creado_en", "fecha_muestreo", "id_gato", "vacunas", "propietario"]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 3}),
            "raza_definida": forms.Select(attrs={"id": "id_raza_definida"}),
            "tipo_raza": forms.Select(attrs={"id": "id_tipo_raza"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando un registro existente, cargar las vacunas
        if self.instance and self.instance.pk and self.instance.vacunas:
            self.fields["vacunas_seleccionadas"].initial = self.instance.vacunas

        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (existing + " form-check-input").strip()
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                # No agregar clase form-control a checkboxes múltiples
                pass
            else:
                field.widget.attrs["class"] = (existing + " form-control").strip()

        # Agregar clase is-invalid a campos con errores
        if self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    existing = self.fields[field_name].widget.attrs.get("class", "")
                    self.fields[field_name].widget.attrs["class"] = (existing + " is-invalid").strip()

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Guardar las vacunas seleccionadas en el campo JSONField
        instance.vacunas = self.cleaned_data.get("vacunas_seleccionadas", [])
        if commit:
            instance.save()
        return instance
