import os
import subprocess
import signal
import socket
import psutil
from time import sleep
from pathlib import Path
from datetime import datetime
import sys
# -------------------------------------
# CONFIGURACIONES
PORT = 8000
HOST = "0.0.0.0"
PROJECT_NAME = "gestion_empresa"
BASE_DIR = Path(__file__).parent.resolve()
LOG_FILE = BASE_DIR / "log_servidor.txt"
VENV_DIRS = ["venv", ".venv"]  # Buscar estos nombres
PYTHON_CMD = "python"  # Default

# -------------------------------------
# FUNCIONES

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{msg}\n")

def kill_processes_on_port(port):
    log(f"🛑 Buscando procesos en el puerto {port}...")
    for proc in psutil.process_iter(attrs=["pid", "name", "connections"]):
        try:
            for conn in proc.info["connections"]:
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    log(f"Matando proceso PID {proc.pid} en puerto {port}")
                    proc.kill()
                    sleep(1)
        except Exception:
            continue

def find_manage_py():
    expected_paths = [
        BASE_DIR / PROJECT_NAME / "manage.py",
        BASE_DIR.parent / PROJECT_NAME / "manage.py"
    ]
    for path in expected_paths:
        if path.exists():
            return path.parent
    log("❌ No se encontró manage.py")
    sys.exit(1)


def activate_virtualenv():
    global PYTHON_CMD
    for venv_name in VENV_DIRS:
        venv_python = BASE_DIR / venv_name / "Scripts" / "python.exe"
        if venv_python.exists():
            PYTHON_CMD = str(venv_python)
            log(f"✅ Entorno virtual activado: {PYTHON_CMD}")
            return
    log("⚠️ No se encontró entorno virtual, usando Python del sistema.")

def iniciar_servidor(proyecto_path):
    os.chdir(proyecto_path)
    log(f"🚀 Iniciando servidor Django en {HOST}:{PORT}...")
    subprocess.Popen(
        f'"{PYTHON_CMD}" manage.py runsslserver {HOST}:{PORT} >> "{LOG_FILE}" 2>&1',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


# -------------------------------------
# EJECUCIÓN

# Sobrescribir el archivo de log al inicio
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write(f"==== LOG DEL SERVIDOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")

kill_processes_on_port(PORT)
activate_virtualenv()
proyecto_path = find_manage_py()
iniciar_servidor(proyecto_path)
