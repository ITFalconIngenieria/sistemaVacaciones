@echo off
setlocal

REM Obtener la ruta del directorio del script
set "script_dir=%~dp0"
set "log_file=%script_dir%server_log.txt"

REM Registrar el inicio
echo. >> "%log_file%"
echo === Iniciando verificación: %date% %time% === >> "%log_file%"

REM Definir rutas
set "project_root=%script_dir%.."
set "venv_python=%project_root%\venv\Scripts\python.exe"
set "project_dir=%project_root%\gestion_empresa"
set "command=python manage.py runsslserver 0.0.0.0:8000"
set "full_command=%venv_python% manage.py runsslserver 0.0.0.0:8000"

REM Cambiar al directorio del proyecto
cd /d "%project_dir%"

REM Buscar si el proceso está corriendo
for /f "tokens=2 delims=," %%a in ('tasklist /v /fo csv ^| findstr /i "manage.py runsslserver"') do (
    echo Proceso encontrado (PID: %%a), terminando... >> "%log_file%"
    taskkill /PID %%a /F >> "%log_file%" 2>&1
    timeout /t 2 >nul
)

REM Iniciar el servidor
echo Iniciando servidor... >> "%log_file%"
start "" cmd /c "%full_command% >> \"%log_file%\" 2>&1"

echo === Verificación finalizada: %date% %time% === >> "%log_file%"
endlocal
