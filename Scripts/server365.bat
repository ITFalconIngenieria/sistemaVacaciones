@echo off
cd /d C:\Users\Administrator\Documents\sistemaVacaciones

:: Definir archivo de log con ruta completa para que funcione independientemente de dónde se ejecute
set LOGFILE=C:\Users\Administrator\Documents\sistemaVacaciones\server_log.txt

:: Registrar inicio del script
echo [%DATE% %TIME%] Iniciando script para gestionar el servidor Django... > %LOGFILE%

:: Mejorar la detección y terminación de procesos existentes
echo [%DATE% %TIME%] Buscando procesos de Django en el puerto 8000... >> %LOGFILE%

:: Buscar todos los PIDs que estén usando el puerto 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo [%DATE% %TIME%] Deteniendo proceso con PID %%a... >> %LOGFILE%
    taskkill /PID %%a /F >> %LOGFILE% 2>&1
    if %ERRORLEVEL% == 0 (
        echo [%DATE% %TIME%] Proceso %%a detenido correctamente. >> %LOGFILE%
    ) else (
        echo [%DATE% %TIME%] ERROR: No se pudo detener el proceso %%a. >> %LOGFILE%
    )
)

:: También buscar procesos de Python que puedan estar ejecutando Django
echo [%DATE% %TIME%] Buscando procesos de Python relacionados con runsslserver... >> %LOGFILE%
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo csv /nh') do (
    tasklist /fi "PID eq %%p" /v | findstr "runsslserver" > nul
    if not %ERRORLEVEL% == 1 (
        echo [%DATE% %TIME%] Deteniendo proceso de Python relacionado con Django (PID: %%p)... >> %LOGFILE%
        taskkill /PID %%p /F >> %LOGFILE% 2>&1
    )
)

:: Esperar a que todos los procesos terminen
timeout /t 3 > nul

:: Activar el entorno virtual
echo [%DATE% %TIME%] Activando entorno virtual... >> %LOGFILE%
call venv\Scripts\activate >> %LOGFILE% 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] ERROR: No se pudo activar el entorno virtual. >> %LOGFILE%
    goto :exit
)

:: Entrar en la carpeta del proyecto
cd gestion_empresa
if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] ERROR: No se pudo acceder a la carpeta del proyecto. >> %LOGFILE%
    goto :exit
)

:: Ejecutar el servidor en segundo plano con una nueva instancia de cmd
echo [%DATE% %TIME%] Iniciando servidor Django en segundo plano... >> ..\%LOGFILE%
start /min cmd /c "python manage.py runsslserver 0.0.0.0:8000 >> ..\%LOGFILE% 2>&1"

:: Mensaje final
echo [%DATE% %TIME%] Servidor ejecutándose en segundo plano. Revisa el archivo %LOGFILE% para detalles. >> ..\%LOGFILE%

:exit
:: Asegurarse de que el script termine, cerrando la ventana actual
echo [%DATE% %TIME%] Finalizando ejecución del script. >> %LOGFILE%
exit