# Actualizaciones del Sistema Zamora Felinos

## Resumen de Cambios

Se han implementado las siguientes mejoras al sistema:

### 1. ID de Gato Auto-generado
- El ID del gato ahora se genera automáticamente usando UUID
- Ya no es necesario ingresar manualmente el ID

### 2. Razas Definidas
- Cuando se selecciona "Raza definida", aparece un selector con razas conocidas:
  - Persa, Siamés, Maine Coon, Bengalí, Ragdoll
  - Británico de Pelo Corto, Abisinio, Sphynx
  - Scottish Fold, Angora Turco, Burmés
  - Bosque de Noruega, Himalayo, y más

### 3. Estado de Salud Detallado
Se eliminaron los campos obsoletos (Hematocrito, Hemólisis, Autoaglutinación, Resultado aglutinación) y se agregaron:
- **Temperatura (°C)**: Temperatura corporal del felino
- **Peso (kg)**: Peso del animal
- **Frecuencia cardíaca (lpm)**: Latidos por minuto
- **Frecuencia respiratoria (rpm)**: Respiraciones por minuto

### 4. Fecha de Muestreo Automática
- La fecha y hora de muestreo ahora se completa automáticamente con la fecha y hora actual

### 5. Sistema de Vacunación
- Checkbox "¿Tiene carnet de vacunación?"
- Si marca "Sí", aparece una lista de vacunas comunes para seleccionar:
  - Triple felina (FVRCP)
  - Rabia
  - Leucemia felina (FeLV)
  - Clamidia
  - Peritonitis infecciosa felina (PIF)
- Si marca "No", simplemente no se muestra la lista

### 6. Datos del Propietario
Se creó un nuevo modelo completo para el propietario con:
- Nombres y Apellidos
- Cédula (única)
- Teléfono
- Correo electrónico
- Dirección
- **Coordenadas geográficas** (latitud y longitud)

### 7. Selector de Ubicación en Mapa
- Mapa interactivo usando Leaflet (OpenStreetMap)
- Centrado en Zamora, Ecuador
- Clic en el mapa para seleccionar la ubicación exacta del domicilio
- Las coordenadas se guardan automáticamente para el mapa de calor del dashboard

### 8. Generación de PDF de Consentimiento
- Botón para descargar el consentimiento informado en PDF
- Incluye todos los datos del propietario y del felino
- Formato profesional con el texto proporcionado
- Línea para firma y fecha automática

## Instrucciones de Instalación

### ⚡ Opción 1: Usando los scripts automáticos (RECOMENDADO)

#### 1. Ejecutar instalación y migraciones
Haz doble clic en el archivo:
```
instalar_y_migrar.bat
```

Este script automáticamente:
- ✅ Activa el entorno conda `clases`
- ✅ Instala reportlab
- ✅ Aplica las migraciones a la base de datos

#### 2. Ejecutar el servidor
Haz doble clic en el archivo:
```
ejecutar_servidor.bat
```

Esto iniciará el servidor en http://127.0.0.1:8000/

---

### 🔧 Opción 2: Comandos manuales

#### 1. Activar el entorno conda

```bash
conda activate clases
```

#### 2. Instalar dependencias nuevas

```bash
pip install reportlab==4.0.7
```

O instalar todo:
```bash
pip install -r requirements.txt
```

#### 3. Aplicar migraciones a la base de datos

```bash
python manage.py migrate
```

Esto creará:
- La tabla `Propietario` con todos sus campos
- Los nuevos campos en `RegistroGato`
- Eliminará los campos obsoletos

#### 4. Crear un superusuario (si aún no lo has hecho)

```bash
python manage.py createsuperuser
```

#### 5. Ejecutar el servidor

```bash
python manage.py runserver
```

## Uso del Sistema

### Crear un Nuevo Registro

1. Ve a "Nuevo registro"
2. Completa los **Datos del Propietario**:
   - Nombres, Apellidos, Cédula, Teléfono, Correo, Dirección
   - Haz clic en el mapa para marcar la ubicación exacta
3. Completa los **Datos del Felino**:
   - El ID se genera automáticamente (no lo ingreses)
   - Selecciona el tipo de raza
   - Si es "Raza definida", selecciona la raza específica
4. Completa el **Estado de Salud**:
   - Temperatura, Peso, Frecuencia cardíaca, Frecuencia respiratoria
5. **Vacunación**:
   - Marca si tiene carnet de vacunación
   - Si tiene, selecciona las vacunas aplicadas
6. Completa **Antecedentes y Resultados**
7. La fecha de muestreo se guardará automáticamente al crear el registro

### Descargar Consentimiento en PDF

1. Edita un registro existente
2. Haz clic en el botón "Descargar Consentimiento (PDF)"
3. Se descargará un PDF con el formato del consentimiento informado

### Propietarios Duplicados

El sistema maneja automáticamente propietarios duplicados:
- Si ingresas una cédula que ya existe, se actualizarán los datos del propietario
- Un propietario puede tener múltiples gatos registrados

## Cambios en la Base de Datos

### Nuevo Modelo: Propietario
```python
- nombres
- apellidos
- cedula (única)
- telefono
- correo
- direccion
- latitud (para mapa de calor)
- longitud (para mapa de calor)
```

### Modelo RegistroGato - Campos Nuevos
```python
- tipo_raza (reemplaza "raza")
- raza_definida (nueva)
- temperatura
- peso
- frecuencia_cardiaca
- frecuencia_respiratoria
- tiene_carnet_vacunacion
- vacunas (JSONField)
- propietario (ForeignKey)
```

### Campos Eliminados
```python
- hematocrito ❌
- hemolisis ❌
- autoaglutinacion ❌
- resultado_aglutinacion ❌
```

### Campos Modificados
```python
- id_gato: Ahora auto-generado con UUID
- fecha_muestreo: Ahora DateTimeField con auto_now_add=True
```

## Próximos Pasos Sugeridos

1. **Mapa de Calor en Dashboard**: Usar las coordenadas de los propietarios para mostrar un mapa de calor con la distribución geográfica de los felinos registrados

2. **Exportación Mejorada**: El CSV ya incluye los nuevos campos, pero podrías agregar exportación a Excel

3. **Reportes**: Generar reportes estadísticos basados en las vacunas, razas, y datos de salud

## Notas Importantes

- **Datos Existentes**: Si tienes registros antiguos, necesitarás crear propietarios para ellos o la migración podría fallar (el campo propietario es nullable temporalmente)

- **Mapa**: Requiere conexión a internet para cargar los tiles de OpenStreetMap

- **PDF**: La librería ReportLab genera PDFs de alta calidad con formato profesional

## Soporte

Si encuentras algún problema con las migraciones o necesitas ayuda, revisa:
1. Que todas las dependencias estén instaladas
2. Que las migraciones se hayan aplicado correctamente
3. Los logs de Django para errores específicos
