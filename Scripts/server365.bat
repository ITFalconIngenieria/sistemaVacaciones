@echo off
cd /d C:\Users\Administrator\Documents\sistemaVacaciones

:: Definir archivo de log
set LOGFILE=server_log.txt
echo [%DATE% %TIME%] Iniciando script para gestionar el servidor Django... > %LOGFILE%

:: Verifica si hay un proceso de Python corriendo en el puerto 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo [%DATE% %TIME%] Servidor detectado en el puerto 8000 con PID %%a. Intentando detenerlo... >> %LOGFILE%
    taskkill /PID %%a /F >> %LOGFILE% 2>&1
    echo [%DATE% %TIME%] Esperando 3 segundos antes de reiniciar... >> %LOGFILE%
    timeout /t 3 >nul
)

:: Activa el entorno virtual
echo [%DATE% %TIME%] Activando entorno virtual... >> %LOGFILE%
call venv\Scripts\activate >> %LOGFILE% 2>&1

:: Entra en la carpeta del proyecto
cd gestion_empresa
echo [%DATE% %TIME%] Iniciando servidor Django en segundo plano... >> ..\%LOGFILE%

:: Ejecuta el servidor en segundo plano
start /min cmd /c python manage.py runsslserver 0.0.0.0:8000 >> ..\%LOGFILE% 2>&1

:: Mensaje final
echo [%DATE% %TIME%] Servidor ejecutándose en segundo plano. Revisa el archivo %LOGFILE% para detalles. >> ..\%LOGFILE%
exit
