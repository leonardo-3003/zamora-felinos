# Zamora Felinos — Recolección de datos y dashboard

App sencilla en Django para registrar los datos de tipificación sanguínea
felina (kit de inmunocromatografía + aglutinación en portaobjetos) y ver
un dashboard con frecuencias, cruces por variable y la concordancia entre
métodos (Kappa de Cohen).

## ⚠️ Nota importante sobre Vercel + Django

Vercel está pensado originalmente para frontends (Next.js, sitios estáticos).
Django funciona ahí como función serverless mediante el builder no oficial
`@vercel/python`, con estas limitaciones que debes tener presentes:

- **No hay filesystem persistente** → la base de datos **debe** ser externa
  (Postgres en Neon o Supabase, ambos con plan gratuito). SQLite no sirve en producción.
- **No hay un paso de "build" que ejecute comandos de Django** (como
  `migrate` o `collectstatic`). Las migraciones se corren **desde tu máquina**
  apuntando a la base de datos de Neon/Supabase (ver abajo). Los estáticos
  los sirve WhiteNoise directamente en modo "finders", sin necesitar collectstatic.
- **Cold starts**: la primera petición después de un tiempo sin uso puede
  tardar unos segundos.
- Si en el futuro el proyecto crece (tareas en segundo plano, websockets,
  cron jobs pesados), un VPS como el que ya usas para Bomberos El Pangui
  va a darte muchos menos dolores de cabeza que Vercel. Para esto, que es
  chico, Vercel funciona bien.

## Estructura

```
config/          # settings, urls, wsgi del proyecto
core/            # app: modelos, vistas, formularios, templates
templates/core/  # HTML (Bootstrap + Chart.js vía CDN, sin build de frontend)
vercel_app.py    # entrypoint WSGI que usa Vercel
vercel.json      # configuración del despliegue
requirements.txt
```

## 1. Desarrollo local

```bash
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # y edítalo si quieres usar Postgres también en local
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sin `DATABASE_URL` en `.env`, el proyecto usa SQLite automáticamente — perfecto para probar en tu máquina.

## 2. Crear la base de datos en Neon (gratis)

1. Crea una cuenta en https://neon.tech y un proyecto nuevo.
2. Copia el "Connection string" (empieza con `postgresql://...?sslmode=require`).
3. Ese valor es tu `DATABASE_URL`.

(Supabase funciona igual: Project Settings → Database → Connection string.)

## 3. Correr las migraciones contra Neon

Desde tu máquina, **antes de tu primer despliegue** y cada vez que cambies modelos:

```bash
export DATABASE_URL="postgresql://usuario:password@ep-xxxx.neon.tech/dbname?sslmode=require"
python manage.py migrate
python manage.py createsuperuser
```

## 4. Desplegar en Vercel

```bash
npm install -g vercel     # si no lo tienes
vercel login
vercel
```

En el dashboard de Vercel (o con `vercel env add`), configura estas variables de entorno:

| Variable | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | una cadena aleatoria larga |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | la cadena de conexión de Neon/Supabase |
| `DJANGO_ALLOWED_HOSTS` | tu-proyecto.vercel.app |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | https://tu-proyecto.vercel.app |

Luego:

```bash
vercel --prod
```

## 5. Uso

- `/login/` — inicio de sesión (solo el equipo de investigación tiene cuentas).
- `/` — dashboard con frecuencias, cruces por sexo/edad/procedencia/estado de
  salud/antecedente transfusional, y el coeficiente Kappa de concordancia
  entre el kit IC y la aglutinación en portaobjetos.
- `/registros/` — listado de todos los registros.
- `/registros/nuevo/` — formulario para capturar un nuevo gato muestreado.
- `/registros/exportar.csv` — descarga de todos los datos en CSV (para SPSS/R).
- `/admin/` — panel de administración de Django (gestión de usuarios, edición masiva).

Para crear cuentas de usuario adicionales (otros investigadores), usa
`python manage.py createsuperuser` o el panel `/admin/`.
