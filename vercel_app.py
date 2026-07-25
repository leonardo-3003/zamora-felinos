"""
Punto de entrada que usa el builder @vercel/python.
Vercel importa este archivo y busca la variable `app` (una aplicación WSGI).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
