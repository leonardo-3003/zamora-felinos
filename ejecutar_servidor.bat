@echo off
echo ====================================
echo Ejecutando servidor Django
echo ====================================
echo.

echo Activando entorno conda clases...
call C:\Users\leona\anaconda3\condabin\conda.bat activate clases

echo.
echo Iniciando servidor en http://127.0.0.1:8000/
echo Presiona Ctrl+C para detener el servidor
echo.
python manage.py runserver
