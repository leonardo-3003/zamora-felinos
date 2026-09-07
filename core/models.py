from urllib.parse import quote

from django.conf import settings
from django.db import models
import uuid


class Propietario(models.Model):
    """Modelo para almacenar información del propietario del felino."""
    # Parroquias y barrios del cantón Zamora
    BARRIOS_ZAMORA = [
        # Parroquia Zamora (urbana)
        ("Centro", "Centro"),
        ("El Limón", "El Limón"),
        ("Jaime Roldós", "Jaime Roldós"),
        ("Tungurahua", "Tungurahua"),
        ("Ciudadela Municipal", "Ciudadela Municipal"),
        ("El Ejido", "El Ejido"),
        ("La Vega", "La Vega"),
        ("Las Palmeras", "Las Palmeras"),
        ("San Francisco", "San Francisco"),
        ("Isidro Ayora", "Isidro Ayora"),
        # Parroquias rurales del cantón Zamora
        ("Cumbaratza", "Cumbaratza"),
        ("Guadalupe", "Guadalupe"),
        ("Imbana", "Imbana"),
        ("Sabanilla", "Sabanilla"),
        ("San Carlos de las Minas", "San Carlos de las Minas"),
        ("Timbara", "Timbara"),
        ("Otro", "Otro"),
    ]

    nombres = models.CharField("Nombres", max_length=100)
    apellidos = models.CharField("Apellidos", max_length=100)
    cedula = models.CharField("Cédula", max_length=20, unique=True)
    telefono = models.CharField("Teléfono", max_length=20)
    correo = models.EmailField("Correo electrónico", blank=True)
    barrio = models.CharField("Barrio/Sector", max_length=50, choices=BARRIOS_ZAMORA, default="Centro")
    # Coordenadas para el mapa de calor
    latitud = models.DecimalField("Latitud", max_digits=10, decimal_places=7, null=True, blank=True)
    longitud = models.DecimalField("Longitud", max_digits=10, decimal_places=7, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Propietario"
        verbose_name_plural = "Propietarios"

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.cedula})"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"


class RegistroGato(models.Model):
    SEXO_CHOICES = [
        ("M", "Macho"),
        ("H", "Hembra"),
    ]
    TIPO_RAZA_CHOICES = [
        ("mestizo", "Mestizo"),
        ("definida", "Raza definida"),
    ]
    # Razas de gatos más comunes
    RAZA_DEFINIDA_CHOICES = [
        ("persa", "Persa"),
        ("siames", "Siamés"),
        ("maine_coon", "Maine Coon"),
        ("bengali", "Bengalí"),
        ("ragdoll", "Ragdoll"),
        ("británico_pelo_corto", "Británico de Pelo Corto"),
        ("abisinio", "Abisinio"),
        ("sphynx", "Sphynx"),
        ("scottish_fold", "Scottish Fold"),
        ("angora", "Angora Turco"),
        ("burmés", "Burmés"),
        ("bosque_noruego", "Bosque de Noruega"),
        ("himalayo", "Himalayo"),
        ("otra", "Otra"),
    ]
    ESTADO_SALUD_CHOICES = [
        ("sano", "Sano"),
        ("enfermo", "Enfermo"),
    ]
    GRUPO_CHOICES = [
        ("A", "A"),
        ("B", "B"),
        ("AB", "AB"),
        ("ND", "No determinable"),
    ]
    # Vacunas comunes para felinos
    VACUNAS_DISPONIBLES = [
        "Triple felina (FVRCP)",
        "Rabia",
        "Leucemia felina (FeLV)",
        "Clamidia",
        "Peritonitis infecciosa felina (PIF)",
    ]

    # ID auto-generado con UUID
    id_gato = models.CharField("ID del gato", max_length=50, unique=True, editable=False, default=uuid.uuid4)
    nombre = models.CharField("Nombre", max_length=100, blank=True)

    # Campos de raza
    tipo_raza = models.CharField("Tipo de raza", max_length=20, choices=TIPO_RAZA_CHOICES, default="mestizo")
    raza_definida = models.CharField("Raza específica", max_length=50, choices=RAZA_DEFINIDA_CHOICES, blank=True, null=True)

    sexo = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES)
    edad_meses = models.PositiveIntegerField("Edad (meses)")

    # Propietario
    propietario = models.ForeignKey(Propietario, on_delete=models.CASCADE, related_name="gatos", verbose_name="Propietario")

    # Estado de salud general
    estado_salud = models.CharField(
        "Estado de salud", max_length=10, choices=ESTADO_SALUD_CHOICES, default="sano"
    )

    # Parámetros de salud detallados
    temperatura = models.DecimalField("Temperatura (°C)", max_digits=4, decimal_places=1, null=True, blank=True)
    peso = models.DecimalField("Peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True)
    frecuencia_cardiaca = models.PositiveIntegerField("Frecuencia cardíaca (lpm)", null=True, blank=True)
    frecuencia_respiratoria = models.PositiveIntegerField("Frecuencia respiratoria (rpm)", null=True, blank=True)

    # Vacunación
    tiene_carnet_vacunacion = models.BooleanField("¿Tiene carnet de vacunación?", default=False)
    vacunas = models.JSONField("Vacunas aplicadas", default=list, blank=True, help_text="Lista de vacunas que tiene el felino")

    antecedente_transfusion = models.BooleanField("Antecedente transfusional", default=False)

    # Resultados de laboratorio
    resultado_kit_ic = models.CharField(
        "Resultado kit inmunocromatografía", max_length=2, choices=GRUPO_CHOICES
    )

    # Fecha y hora de muestreo auto-completada
    fecha_muestreo = models.DateTimeField("Fecha y hora de muestreo", auto_now_add=True)

    observaciones = models.TextField("Observaciones", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_muestreo", "-creado_en"]
        verbose_name = "Registro de gato"
        verbose_name_plural = "Registros de gatos"

    def __str__(self):
        return f"{self.id_gato} ({self.get_resultado_kit_ic_display()})"

    @property
    def grupo_edad(self):
        """Clasificación etaria usada en el estudio: Cachorro / Adulto / Senil."""
        if self.edad_meses < 12:
            return "Cachorro (<12 m)"
        elif self.edad_meses <= 84:
            return "Adulto (1-7 a)"
        return "Senil (>7 a)"

    @property
    def whatsapp_url(self):
        """Enlace de WhatsApp Click-to-Chat para avisarle al propietario el
        resultado de este registro. WhatsApp no permite adjuntar archivos vía
        enlace (solo pre-llenar texto), así que el certificado se adjunta a
        mano desde el chat que se abre."""
        digitos = "".join(ch for ch in self.propietario.telefono if ch.isdigit())
        if not digitos:
            return None
        if digitos.startswith("593"):
            numero = digitos
        elif digitos.startswith("0"):
            numero = "593" + digitos[1:]
        else:
            numero = "593" + digitos

        mensaje = (
            f"Hola {self.propietario.nombres}, te escribimos del estudio de "
            f"tipificación sanguínea felina de la Universidad Nacional de Loja. "
            f"Te compartimos el certificado con el resultado de tu gato "
            f"{self.nombre or 'sin nombre registrado'}: grupo sanguíneo "
            f"{self.get_resultado_kit_ic_display()}. ¡Gracias por participar!"
        )
        return f"https://wa.me/{numero}?text={quote(mensaje)}"
