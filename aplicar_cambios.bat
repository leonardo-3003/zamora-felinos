@echo off
echo =============================================
echo Aplicando cambios al sistema Zamora Felinos
echo =============================================
echo.

call conda activate clases

echo 1. Creando migraciones...
python manage.py makemigrations core

echo.
echo 2. Aplicando migraciones a la base de datos...
python manage.py migrate

echo.
echo =============================================
echo Cambios aplicados exitosamente!
echo =============================================
echo.
echo Puedes ejecutar el servidor con: ejecutar_servidor.bat
pause
