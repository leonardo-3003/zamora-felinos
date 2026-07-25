@echo off
call conda activate clases
python manage.py makemigrations core --name remove_direccion_field
pause
