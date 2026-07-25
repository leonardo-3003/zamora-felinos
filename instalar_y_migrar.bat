@echo off
echo ====================================
echo Instalando dependencias y migrando
echo ====================================
echo.

echo Activando entorno conda clases...
call C:\Users\leona\anaconda3\condabin\conda.bat activate clases

echo.
echo Instalando reportlab (si no esta instalado)...
pip install reportlab==4.0.7

echo.
echo Aplicando migraciones a la base de datos...
python manage.py migrate

echo.
echo ====================================
echo Instalacion completada exitosamente!
echo ====================================
echo.
echo CAMBIOS APLICADOS:
echo - Agregado campo Barrio/Sector al Propietario
echo - Eliminado campo Procedencia duplicado del Gato
echo - Direccion ahora es opcional
echo.
echo Para ejecutar el servidor, usa:
echo     python manage.py runserver
echo.
pause
