import csv
import re
import unicodedata
from collections import Counter
from io import BytesIO
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.db.models import Avg, Max, Min
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage,
)

from .forms import RegistroGatoForm, PropietarioForm
from .models import RegistroGato, Propietario
from .stats import crosstab

GRUPOS = ["A", "B", "AB", "ND"]


def _fila_logos_colaboradores(ancho_util):
    """Fila con los logos de los consultorios veterinarios que hacen el
    muestreo en campo, para el pie de los PDFs. La proporción de cada logo se
    lee de la imagen real (no se asume un tamaño fijo) para que ambos se vean
    de la misma altura sin deformarse. Si algún logo no se encuentra en disco
    simplemente se omite (no debe romper el PDF)."""
    ALTO_LOGO = 0.45 * inch
    logos = []
    for archivo in ("img/colaboradores/camachito.png", "img/colaboradores/valarezo.png"):
        ruta = finders.find(archivo)
        if ruta:
            ancho_natural, alto_natural = ImageReader(ruta).getSize()
            ancho_logo = ALTO_LOGO * (ancho_natural / alto_natural)
            logos.append(RLImage(ruta, width=ancho_logo, height=ALTO_LOGO))
    if not logos:
        return None
    fila = Table([logos], colWidths=[ancho_util / len(logos)] * len(logos))
    fila.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return fila


def _nombre_archivo_amigable(texto):
    """Convierte un texto libre (ej. el nombre de un gato) en algo seguro y
    legible para un nombre de archivo — sin acentos, espacios ni símbolos que
    se vean mal cuando el PDF se comparte por WhatsApp/correo."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_")
    return texto or "SinNombre"


def _generar_insights(total, frecuencias, registros):
    """Conclusiones cortas en lenguaje simple a partir de los datos agregados
    del dashboard, para que se entiendan de un vistazo sin tener que leer las
    tablas cruzadas (ej. "la mayoría de los gatos son del grupo A")."""
    if total == 0:
        return []

    insights = []

    grupo_top, conteo_grupo_top = max(frecuencias.items(), key=lambda kv: kv[1])
    if conteo_grupo_top > 0:
        etiqueta_grupo = "no determinable" if grupo_top == "ND" else grupo_top
        pct = round(conteo_grupo_top / total * 100)
        insights.append(
            f"La mayoría de los gatos son del grupo sanguíneo {etiqueta_grupo} "
            f"({conteo_grupo_top} de {total}, {pct}%)."
        )

    sanos = sum(1 for r in registros if r["estado_salud"] == "sano")
    pct_sanos = round(sanos / total * 100)
    insights.append(f"El {pct_sanos}% de los gatos muestreados están sanos ({sanos} de {total}).")

    hembras = sum(1 for r in registros if r["sexo"] == "H")
    machos = total - hembras
    sexo_top = "hembras" if hembras >= machos else "machos"
    conteo_sexo_top = max(hembras, machos)
    pct_sexo = round(conteo_sexo_top / total * 100)
    insights.append(f"Predominan los gatos {sexo_top} ({conteo_sexo_top} de {total}, {pct_sexo}%).")

    EDAD_FRASES = {
        "Cachorro (<12 m)": "cachorros (menores de 12 meses)",
        "Adulto (1-7 a)": "adultos (entre 1 y 7 años)",
        "Senil (>7 a)": "adultos mayores (más de 7 años)",
    }
    conteo_edad = Counter(r["grupo_edad"] for r in registros)
    edad_top, conteo_edad_top = conteo_edad.most_common(1)[0]
    pct_edad = round(conteo_edad_top / total * 100)
    insights.append(
        f"La mayoría son gatos {EDAD_FRASES.get(edad_top, edad_top)} "
        f"({conteo_edad_top} de {total}, {pct_edad}%)."
    )

    con_transfusion = sum(1 for r in registros if r["antecedente_transfusion"])
    if con_transfusion > 0:
        pct_transf = round(con_transfusion / total * 100)
        if con_transfusion == 1:
            insights.append(f"1 gato ({pct_transf}%) tiene antecedente transfusional.")
        else:
            insights.append(f"{con_transfusion} gatos ({pct_transf}%) tienen antecedente transfusional.")

    return insights


def dashboard(request):
    """Panel público con estadísticas agregadas. El mapa con la ubicación
    exacta de cada domicilio SOLO se calcula y se envía al navegador si hay
    una sesión iniciada — los propietarios firmaron un consentimiento que
    promete confidencialidad, así que esos datos no deben quedar expuestos
    (ni siquiera en el HTML/JSON de la página) para visitantes anónimos."""
    registros = list(
        RegistroGato.objects.select_related('propietario').all().values(
            "resultado_kit_ic",
            "sexo",
            "estado_salud",
            "antecedente_transfusion",
            "propietario__barrio",
            "edad_meses",
        )
    )
    total = len(registros)

    # Conteo agregado (no identificable) de registros con ubicación: se
    # puede mostrar siempre. Las coordenadas y nombres detallados del mapa
    # de calor solo se arman para usuarios autenticados.
    con_ubicacion_qs = RegistroGato.objects.filter(
        propietario__latitud__isnull=False, propietario__longitud__isnull=False
    )
    total_con_ubicacion = con_ubicacion_qs.count()

    coordenadas = []
    if request.user.is_authenticated:
        # Convertidas a tipos nativos de Python: values_list trae Decimal/tuplas,
        # que no son JSON-serializables directamente para el <script> del template.
        coordenadas = [
            [float(lat), float(lng), nombre, resultado]
            for lat, lng, nombre, resultado in con_ubicacion_qs
            .select_related('propietario')
            .values_list('propietario__latitud', 'propietario__longitud', 'nombre', 'resultado_kit_ic')
        ]

    # Frecuencias del grupo sanguíneo (kit de inmunocromatografía = referencia)
    frecuencias = {g: 0 for g in GRUPOS}
    for r in registros:
        frecuencias[r["resultado_kit_ic"]] = frecuencias.get(r["resultado_kit_ic"], 0) + 1

    # Grupo etario calculado en Python (no existe como columna en la BD)
    for r in registros:
        meses = r["edad_meses"]
        if meses < 12:
            r["grupo_edad"] = "Cachorro (<12 m)"
        elif meses <= 84:
            r["grupo_edad"] = "Adulto (1-7 a)"
        else:
            r["grupo_edad"] = "Senil (>7 a)"

    # Antecedente transfusional legible
    for r in registros:
        r["antecedente_legible"] = "Sí" if r["antecedente_transfusion"] else "No"

    cruces = {
        "Sexo": crosstab(registros, "sexo", GRUPOS),
        "Grupo etario": crosstab(registros, "grupo_edad", GRUPOS),
        "Estado de salud": crosstab(registros, "estado_salud", GRUPOS),
        "Antecedente transfusional": crosstab(registros, "antecedente_legible", GRUPOS),
    }

    # Hematocrito: es un dato de laboratorio opcional (no todos los registros
    # antiguos lo tienen), así que se agrega aparte con un conteo propio en
    # vez de asumir que "total" y "con hematocrito" son el mismo número.
    con_hematocrito_qs = RegistroGato.objects.filter(hematocrito__isnull=False)
    total_con_hematocrito = con_hematocrito_qs.count()
    hematocrito_stats = con_hematocrito_qs.aggregate(
        promedio=Avg("hematocrito"), minimo=Min("hematocrito"), maximo=Max("hematocrito"),
    )

    insights = _generar_insights(total, frecuencias, registros)

    contexto = {
        "total": total,
        "frecuencias": frecuencias,
        "cruces": cruces,
        "insights": insights,
        "grupos_labels": GRUPOS,
        "frecuencias_valores": [frecuencias[g] for g in GRUPOS],
        "coordenadas": coordenadas,
        "total_con_ubicacion": total_con_ubicacion,
        "total_con_hematocrito": total_con_hematocrito,
        "hematocrito_promedio": hematocrito_stats["promedio"],
        "hematocrito_minimo": hematocrito_stats["minimo"],
        "hematocrito_maximo": hematocrito_stats["maximo"],
    }
    return render(request, "core/dashboard.html", contexto)


class RegistroListView(LoginRequiredMixin, ListView):
    model = RegistroGato
    template_name = "core/registro_list.html"
    context_object_name = "registros"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Si venimos de crear un registro nuevo, dispara la descarga automática
        # del PDF de consentimiento para ese registro (ver RegistroCreateView).
        nuevo_pdf = self.request.GET.get("nuevo_pdf", "")
        if nuevo_pdf.isdigit() and RegistroGato.objects.filter(pk=nuevo_pdf).exists():
            context["nuevo_pdf_id"] = int(nuevo_pdf)
        return context


class RegistroCreateView(LoginRequiredMixin, CreateView):
    model = RegistroGato
    form_class = RegistroGatoForm
    template_name = "core/registro_form.html"

    def get_success_url(self):
        # Al terminar de crear el registro, la lista dispara automáticamente
        # la descarga del PDF de consentimiento de este registro recién creado.
        return f"{reverse('registro_list')}?nuevo_pdf={self.object.pk}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["propietarios"] = Propietario.objects.order_by("apellidos", "nombres")
        if self.request.POST:
            context["propietario_form"] = PropietarioForm(self.request.POST)
        else:
            context["propietario_form"] = PropietarioForm()
        return context

    def form_valid(self, form):
        # Si se eligió un propietario ya registrado (para un gato adicional
        # de la misma persona), lo usamos directamente y ni siquiera se valida
        # el formulario de propietario — sus campos llegan vacíos a propósito.
        propietario_id = self.request.POST.get("propietario_id")
        if propietario_id:
            propietario = get_object_or_404(Propietario, pk=propietario_id)
        else:
            context = self.get_context_data()
            propietario_form = context["propietario_form"]
            if not propietario_form.is_valid():
                return self.form_invalid(form)
            propietario = propietario_form.save()

        form.instance.propietario = propietario
        form.instance.registrado_por = self.request.user
        messages.success(self.request, "Registro guardado correctamente.")
        return super().form_valid(form)


class RegistroUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroGato
    form_class = RegistroGatoForm
    template_name = "core/registro_form.html"
    success_url = reverse_lazy("registro_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["propietario_form"] = PropietarioForm(self.request.POST, instance=self.object.propietario)
        else:
            context["propietario_form"] = PropietarioForm(instance=self.object.propietario)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        propietario_form = context["propietario_form"]

        if propietario_form.is_valid():
            propietario_form.save()
            messages.success(self.request, "Registro actualizado correctamente.")
            return super().form_valid(form)
        else:
            return self.form_invalid(form)


@login_required
def exportar_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="registros_zamora_felinos.csv"'

    writer = csv.writer(response)
    # Encabezados del CSV
    writer.writerow([
        "id_gato", "nombre", "tipo_raza", "raza_definida", "sexo", "edad_meses",
        "propietario_cedula", "propietario_nombres", "propietario_apellidos", "barrio",
        "estado_salud", "temperatura", "peso", "frecuencia_cardiaca", "frecuencia_respiratoria",
        "tiene_carnet_vacunacion", "antecedente_transfusion", "resultado_kit_ic", "hematocrito",
        "fecha_muestreo", "observaciones",
    ])

    # Obtener datos con relaciones
    for r in RegistroGato.objects.select_related('propietario').all():
        writer.writerow([
            r.id_gato, r.nombre, r.tipo_raza, r.raza_definida, r.sexo, r.edad_meses,
            r.propietario.cedula, r.propietario.nombres, r.propietario.apellidos, r.propietario.barrio,
            r.estado_salud, r.temperatura, r.peso, r.frecuencia_cardiaca, r.frecuencia_respiratoria,
            r.tiene_carnet_vacunacion, r.antecedente_transfusion, r.resultado_kit_ic, r.hematocrito,
            r.fecha_muestreo, r.observaciones,
        ])

    return response


@login_required
def generar_consentimiento_pdf(request, registro_id):
    """Genera el PDF (a una sola página) del consentimiento informado de un registro."""
    registro = get_object_or_404(RegistroGato.objects.select_related("propietario"), pk=registro_id)
    propietario = registro.propietario

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    story = []
    styles = getSampleStyleSheet()
    ancho_util = doc.width  # 8.5in - márgenes izq/der

    NAVY = colors.HexColor("#0f3f5f")
    TEAL = colors.HexColor("#1c7d71")
    LIGHT_BLUE = colors.HexColor("#e8f2f5")
    LIGHT_ORANGE = colors.HexColor("#fdf1ea")
    GRAY = colors.HexColor("#6b7b7a")
    BORDER = colors.HexColor("#d8dedd")

    institucion_style = ParagraphStyle(
        "Institucion", parent=styles["Normal"], fontSize=8.8, textColor=colors.white,
        alignment=1, fontName="Helvetica",
    )
    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], fontSize=15, textColor=colors.white,
        alignment=1, fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=0, leading=17,
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#cfe8e3"),
        alignment=1, fontName="Helvetica-Oblique",
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=8.5, textColor=GRAY, alignment=2,
    )
    normal_style = ParagraphStyle(
        "CustomNormal", parent=styles["Normal"], fontSize=9.3, leading=12.8, alignment=4,
    )
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8.7, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=8.7, fontName="Helvetica")
    header_cell_style = ParagraphStyle(
        "HeaderCell", parent=styles["Normal"], fontSize=9.3, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=1,
    )
    firma_caption_style = ParagraphStyle(
        "FirmaCaption", parent=styles["Normal"], fontSize=8.3, alignment=1, textColor=GRAY, leading=11,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=7.3, textColor=GRAY, alignment=1,
    )

    def lbl(texto):
        return Paragraph(texto, label_style)

    def val(texto):
        return Paragraph(str(texto), value_style)

    # --- Encabezado institucional -------------------------------------
    encabezado = Table(
        [
            [Paragraph("UNIVERSIDAD NACIONAL DE LOJA · MAESTRÍA EN MEDICINA VETERINARIA", institucion_style)],
            [Paragraph("CONSENTIMIENTO INFORMADO", titulo_style)],
            [Paragraph("Estudio de prevalencia de grupos sanguíneos felinos en el cantón Zamora, Ecuador", subtitulo_style)],
        ],
        colWidths=[ancho_util],
    )
    encabezado.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (0, 0), 9),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1),
        ("TOPPADDING", (0, 1), (0, 1), 1),
        ("BOTTOMPADDING", (0, 1), (0, 1), 1),
        ("TOPPADDING", (0, 2), (0, 2), 1),
        ("BOTTOMPADDING", (0, 2), (0, 2), 10),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 0.18 * inch))

    # --- Trazabilidad del documento ------------------------------------
    story.append(Paragraph(
        f"Código de registro: <b>{registro.id_gato}</b> &middot; "
        f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}",
        meta_style,
    ))
    story.append(Spacer(1, 0.1 * inch))

    # --- Texto del consentimiento --------------------------------------
    nombre_felino = registro.nombre if registro.nombre else "sin nombre registrado"
    texto_consentimiento = f"""
    Yo, <b>{propietario.nombre_completo}</b>, con cédula <b>{propietario.cedula}</b>, propietario(a) del felino
    <b>{nombre_felino}</b>, autorizo al equipo de investigación de la Maestría en Medicina Veterinaria de la
    Universidad Nacional de Loja a realizar la toma de una muestra de sangre (1&#8211;2 mL) mediante venopunción
    de la vena cefálica (miembro anterior) o safena medial (miembro posterior) de mi animal, con fines
    exclusivamente académicos y de investigación científica. Entiendo que el procedimiento es mínimamente
    invasivo, que mi participación es voluntaria y que los datos obtenidos serán tratados de forma confidencial,
    utilizados únicamente para este estudio de prevalencia de grupos sanguíneos felinos en el cantón Zamora.
    """
    story.append(Paragraph(texto_consentimiento, normal_style))
    story.append(Spacer(1, 0.22 * inch))

    # --- Tabla combinada: propietario + felino -------------------------
    raza_completa = registro.get_tipo_raza_display()
    if registro.raza_definida:
        raza_completa += f" – {registro.get_raza_definida_display()}"

    filas = [
        [
            Paragraph("DATOS DEL PROPIETARIO", header_cell_style), "",
            Paragraph("DATOS DEL FELINO", header_cell_style), "",
        ],
        [lbl("Nombres y apellidos"), val(propietario.nombre_completo), lbl("Nombre"), val(nombre_felino)],
        [lbl("Cédula"), val(propietario.cedula), lbl("Raza"), val(raza_completa)],
        [lbl("Teléfono"), val(propietario.telefono), lbl("Sexo"), val(registro.get_sexo_display())],
        [
            lbl("Correo electrónico"), val(propietario.correo or "No proporcionado"),
            lbl("Edad"), val(f"{registro.edad_meses} meses ({registro.grupo_edad})"),
        ],
        [lbl("Barrio/Sector"), val(propietario.barrio), lbl("Estado de salud"), val(registro.get_estado_salud_display())],
    ]

    col_w = [ancho_util * 0.185, ancho_util * 0.315, ancho_util * 0.17, ancho_util * 0.33]
    tabla = Table(filas, colWidths=col_w)
    tabla.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (2, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (1, 0), NAVY),
        ("BACKGROUND", (2, 0), (3, 0), TEAL),
        ("BACKGROUND", (0, 1), (0, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 1), (2, -1), LIGHT_ORANGE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 1), (-1, -1), 0.4, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#c7d0cf")),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 0.3 * inch))

    # --- Firma -----------------------------------------------------------
    firma_tabla = Table(
        [
            ["", ""],
            [
                Paragraph(f"Firma del propietario<br/>C.I. {propietario.cedula}", firma_caption_style),
                Paragraph(f"Zamora, Ecuador &mdash; {datetime.now().strftime('%d/%m/%Y')}", firma_caption_style),
            ],
        ],
        colWidths=[ancho_util / 2, ancho_util / 2],
        rowHeights=[0.5 * inch, None],
    )
    firma_tabla.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.8, colors.black),
        ("LINEBELOW", (1, 0), (1, 0), 0.8, colors.black),
        ("LEFTPADDING", (0, 0), (0, -1), 0.4 * inch),
        ("RIGHTPADDING", (0, 0), (0, -1), 0.4 * inch),
        ("LEFTPADDING", (1, 0), (1, -1), 0.4 * inch),
        ("RIGHTPADDING", (1, 0), (1, -1), 0.4 * inch),
        ("TOPPADDING", (0, 1), (-1, 1), 5),
    ]))
    story.append(firma_tabla)
    story.append(Spacer(1, 0.25 * inch))

    # --- Pie de página ---------------------------------------------------
    fila_logos = _fila_logos_colaboradores(ancho_util)
    if fila_logos:
        story.append(Paragraph("Muestreo en campo realizado por", footer_style))
        story.append(Spacer(1, 0.05 * inch))
        story.append(fila_logos)
        story.append(Spacer(1, 0.08 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Documento generado automáticamente por el sistema Zamora Felinos &middot; "
        f"Emitido el {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        footer_style,
    ))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    nombre_archivo = _nombre_archivo_amigable(registro.nombre or propietario.apellidos)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Consentimiento_{nombre_archivo}.pdf"'
    response.write(pdf)

    return response


# Colores por grupo sanguíneo para el sello del certificado — los mismos usados
# en el dashboard (validados para ser distinguibles con daltonismo); "ND" usa
# el gris neutro en vez de un color de grupo real.
COLOR_POR_GRUPO = {
    "A": colors.HexColor("#2a78d6"),
    "B": colors.HexColor("#eb6834"),
    "AB": colors.HexColor("#1baf7a"),
    "ND": colors.HexColor("#898781"),
}


@login_required
def generar_certificado_pdf(request, registro_id):
    """Genera el PDF (a una sola página) del certificado de resultado de
    tipificación sanguínea de un registro, para enviarle al propietario."""
    registro = get_object_or_404(RegistroGato.objects.select_related("propietario"), pk=registro_id)
    propietario = registro.propietario

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    story = []
    styles = getSampleStyleSheet()
    ancho_util = doc.width

    NAVY = colors.HexColor("#0f3f5f")
    TEAL = colors.HexColor("#1c7d71")
    LIGHT_BLUE = colors.HexColor("#e8f2f5")
    GRAY = colors.HexColor("#6b7b7a")
    BORDER = colors.HexColor("#d8dedd")
    color_grupo = COLOR_POR_GRUPO.get(registro.resultado_kit_ic, COLOR_POR_GRUPO["ND"])

    institucion_style = ParagraphStyle(
        "Institucion", parent=styles["Normal"], fontSize=8.8, textColor=colors.white,
        alignment=1, fontName="Helvetica",
    )
    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], fontSize=15, textColor=colors.white,
        alignment=1, fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=0, leading=17,
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#cfe8e3"),
        alignment=1, fontName="Helvetica-Oblique",
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=8.5, textColor=GRAY, alignment=2,
    )
    normal_style = ParagraphStyle(
        "CustomNormal", parent=styles["Normal"], fontSize=9.3, leading=12.8, alignment=4,
    )
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8.7, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=8.7, fontName="Helvetica")
    header_cell_style = ParagraphStyle(
        "HeaderCell", parent=styles["Normal"], fontSize=9.3, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=1,
    )
    grupo_letra_style = ParagraphStyle(
        "GrupoLetra", parent=styles["Normal"], fontSize=40, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=1, leading=44,
    )
    grupo_caption_style = ParagraphStyle(
        "GrupoCaption", parent=styles["Normal"], fontSize=8.7, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=1,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=7.3, textColor=GRAY, alignment=1,
    )

    def lbl(texto):
        return Paragraph(texto, label_style)

    def val(texto):
        return Paragraph(str(texto), value_style)

    # --- Encabezado institucional -------------------------------------
    encabezado = Table(
        [
            [Paragraph("UNIVERSIDAD NACIONAL DE LOJA · MAESTRÍA EN MEDICINA VETERINARIA", institucion_style)],
            [Paragraph("CERTIFICADO DE TIPIFICACIÓN SANGUÍNEA", titulo_style)],
            [Paragraph("Estudio de prevalencia de grupos sanguíneos felinos en el cantón Zamora, Ecuador", subtitulo_style)],
        ],
        colWidths=[ancho_util],
    )
    encabezado.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (0, 0), 9),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1),
        ("TOPPADDING", (0, 1), (0, 1), 1),
        ("BOTTOMPADDING", (0, 1), (0, 1), 1),
        ("TOPPADDING", (0, 2), (0, 2), 1),
        ("BOTTOMPADDING", (0, 2), (0, 2), 10),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 0.18 * inch))

    # --- Trazabilidad del documento ------------------------------------
    story.append(Paragraph(
        f"Código de registro: <b>{registro.id_gato}</b> &middot; "
        f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}",
        meta_style,
    ))
    story.append(Spacer(1, 0.15 * inch))

    # --- Sello grande con el grupo sanguíneo ----------------------------
    nombre_felino = registro.nombre if registro.nombre else "sin nombre registrado"
    sello = Table(
        [
            [Paragraph(f"Resultado para {nombre_felino}", header_cell_style)],
            [Paragraph(registro.get_resultado_kit_ic_display() if registro.resultado_kit_ic == "ND" else registro.resultado_kit_ic, grupo_letra_style)],
            [Paragraph("GRUPO SANGUÍNEO (kit de inmunocromatografía)", grupo_caption_style)],
        ],
        colWidths=[ancho_util],
    )
    sello.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color_grupo),
        ("TOPPADDING", (0, 0), (0, 0), 10),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 2),
        ("BOTTOMPADDING", (0, 1), (0, 1), 2),
        ("TOPPADDING", (0, 2), (0, 2), 2),
        ("BOTTOMPADDING", (0, 2), (0, 2), 12),
    ]))
    story.append(sello)
    story.append(Spacer(1, 0.22 * inch))

    story.append(Paragraph(
        f"Se certifica que, dentro del estudio de tipificación sanguínea felina realizado en el cantón "
        f"Zamora, se tomó una muestra de sangre del felino <b>{nombre_felino}</b>, propiedad de "
        f"<b>{propietario.nombre_completo}</b>, cuyo resultado mediante kit de inmunocromatografía se "
        f"detalla arriba. Este resultado tiene fines académicos y de investigación; se recomienda "
        f"confirmarlo con un médico veterinario antes de cualquier procedimiento clínico, en especial "
        f"transfusiones.",
        normal_style,
    ))
    story.append(Spacer(1, 0.22 * inch))

    # --- Tabla combinada: propietario + felino -------------------------
    raza_completa = registro.get_tipo_raza_display()
    if registro.raza_definida:
        raza_completa += f" – {registro.get_raza_definida_display()}"

    filas = [
        [
            Paragraph("DATOS DEL PROPIETARIO", header_cell_style), "",
            Paragraph("DATOS DEL FELINO", header_cell_style), "",
        ],
        [lbl("Nombres y apellidos"), val(propietario.nombre_completo), lbl("Nombre"), val(nombre_felino)],
        [lbl("Cédula"), val(propietario.cedula), lbl("Raza"), val(raza_completa)],
        [lbl("Teléfono"), val(propietario.telefono), lbl("Sexo"), val(registro.get_sexo_display())],
        [
            lbl("Barrio/Sector"), val(propietario.barrio),
            lbl("Edad"), val(f"{registro.edad_meses} meses ({registro.grupo_edad})"),
        ],
        [
            lbl("Fecha de muestreo"), val(registro.fecha_muestreo.strftime("%d/%m/%Y")),
            lbl("Estado de salud"), val(registro.get_estado_salud_display()),
        ],
    ]
    hematocrito_row = None
    if registro.hematocrito is not None:
        filas.append([lbl("Hematocrito"), val(f"{registro.hematocrito} %"), "", ""])
        hematocrito_row = len(filas) - 1

    col_w = [ancho_util * 0.185, ancho_util * 0.315, ancho_util * 0.17, ancho_util * 0.33]
    tabla = Table(filas, colWidths=col_w)
    estilos_tabla = [
        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (2, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (1, 0), NAVY),
        ("BACKGROUND", (2, 0), (3, 0), TEAL),
        ("BACKGROUND", (0, 1), (0, -1), LIGHT_BLUE),
        ("BACKGROUND", (2, 1), (2, -1), LIGHT_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 1), (-1, -1), 0.4, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#c7d0cf")),
    ]
    if hematocrito_row is not None:
        # La fila del hematocrito solo tiene una etiqueta/valor — la celda de
        # valor se extiende sobre las columnas restantes en vez de dejarlas
        # vacías con el resaltado de la columna "Datos del felino".
        estilos_tabla.append(("SPAN", (1, hematocrito_row), (3, hematocrito_row)))
        estilos_tabla.append(("BACKGROUND", (2, hematocrito_row), (3, hematocrito_row), colors.white))
    tabla.setStyle(TableStyle(estilos_tabla))
    story.append(tabla)
    story.append(Spacer(1, 0.3 * inch))

    # --- Pie de página ---------------------------------------------------
    fila_logos = _fila_logos_colaboradores(ancho_util)
    if fila_logos:
        story.append(Paragraph("Muestreo en campo realizado por", footer_style))
        story.append(Spacer(1, 0.05 * inch))
        story.append(fila_logos)
        story.append(Spacer(1, 0.08 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Documento generado automáticamente por el sistema Zamora Felinos &middot; "
        f"Emitido el {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        footer_style,
    ))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    nombre_archivo = _nombre_archivo_amigable(registro.nombre or propietario.apellidos)
    grupo_archivo = _nombre_archivo_amigable(registro.get_resultado_kit_ic_display())
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Certificado_{nombre_archivo}_Grupo_{grupo_archivo}.pdf"'
    response.write(pdf)

    return response
