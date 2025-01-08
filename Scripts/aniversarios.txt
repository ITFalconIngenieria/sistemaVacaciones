@echo off
REM Obtener la ruta del directorio del script
set "script_dir=%~dp0"
set "log_file=%script_dir%script_logs.txt"

REM Registrar el inicio de la ejecución
echo. >> "%log_file%"
echo === Ejecución iniciada: %date% %time% === >> "%log_file%"

REM Definir rutas y comandos
set "project_root=%script_dir%.."
set "venv_activate=%project_root%\venv\Scripts\activate"
set "project_dir=%project_root%\gestion_empresa"
set "command=python manage.py check_aniversarios"

REM Validar si el directorio del proyecto existe
if not exist "%project_dir%" (
    echo El directorio del proyecto no existe: %project_dir% >> "%log_file%"
    echo Error: El directorio del proyecto no existe.
    goto end
)

REM Cambiar al directorio del proyecto
cd /d "%project_dir%"

REM Verificar si el entorno virtual existe
if exist "%venv_activate%" (
    set "full_command=%project_root%\venv\Scripts\python.exe manage.py check_aniversarios"
    echo Entorno virtual encontrado. Ejecutando con python del entorno virtual. >> "%log_file%"
) else (
    set "full_command=%command%"
    echo No se encontró un entorno virtual. Ejecutando comando directamente. >> "%log_file%"
)

REM Ejecutar el comando
for /f "tokens=*" %%i in ('%full_command% 2^>^&1') do (
    echo %%i >> "%log_file%"
)

REM Registrar la finalización de la ejecución
echo === Ejecución terminada: %date% %time% === >> "%log_file%"

:end
