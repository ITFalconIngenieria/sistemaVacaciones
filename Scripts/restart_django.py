import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import psutil
from time import sleep

# -------------------------------
# CONFIGURACIONES
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
PROJECT_DIR = PROJECT_ROOT / "gestion_empresa"
LOG_FILE = SCRIPT_DIR / "log_servidor.txt"
PYTHON_CMD = "python"  # por defecto

# -------------------------------
# FUNCIONES

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def kill_processes_on_port(port):
    log(f"🛑 Buscando procesos en el puerto {port}...")
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            for conn in proc.net_connections(kind='inet'):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    log(f"Matando proceso PID {proc.pid} en puerto {port}")
                    proc.kill()
                    sleep(1)
        except Exception:
            continue



def detect_python_cmd():
    global PYTHON_CMD
    for exe_name in ["pythonw.exe", "python.exe"]:
        candidate = PROJECT_ROOT / "venv" / "Scripts" / exe_name
        if candidate.exists():
            PYTHON_CMD = str(candidate)
            log(f"✅ Entorno virtual detectado: {PYTHON_CMD}")
            return
    log("⚠️ No se encontró entorno virtual. Se usará Python del sistema.")

def iniciar_servidor():
    if not PROJECT_DIR.exists():
        log(f"❌ No se encontró el directorio del proyecto: {PROJECT_DIR}")
        sys.exit(1)

    manage_py = PROJECT_DIR / "manage.py"
    if not manage_py.exists():
        log(f"❌ No se encontró manage.py en: {PROJECT_DIR}")
        sys.exit(1)

    os.chdir(PROJECT_DIR)
    log("🚀 Iniciando servidor Django...")
    subprocess.Popen(
        f'"{PYTHON_CMD}" manage.py runsslserver 0.0.0.0:8000 >> "{str(LOG_FILE)}" 2>&1',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


# -------------------------------
# EJECUCIÓN PRINCIPAL

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write(f"==== LOG DEL SERVIDOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")

kill_processes_on_port(8000)
detect_python_cmd()
iniciar_servidor()
