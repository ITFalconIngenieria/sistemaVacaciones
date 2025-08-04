import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import psutil
from time import sleep
import socket

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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except PermissionError:
        print(f"⚠️ No se pudo escribir en el log (archivo en uso): {msg}")

def kill_processes_on_port(port):
    log(f"🛑 Buscando procesos en el puerto {port}...")
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            conns = proc.net_connections(kind='inet')
            for conn in conns:
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    log(f"Matando proceso PID {proc.pid} que usaba el puerto {port}")
                    proc.kill()
                    proc.wait(timeout=5)
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    sleep(1)

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

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            subprocess.Popen(
                [PYTHON_CMD, "manage.py", "runsslserver", "0.0.0.0:8000"],
                stdout=log_file,
                stderr=log_file,
                cwd=PROJECT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        log("✅ Servidor lanzado correctamente.")
    except Exception as e:
        log(f"❌ Error al iniciar el servidor: {str(e)}")

def esperar_puerto_activo(puerto, timeout=20):
    log(f"⏳ Esperando a que el puerto {puerto} esté activo...")
    for i in range(timeout):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            resultado = sock.connect_ex(('127.0.0.1', puerto))
            if resultado == 0:
                log(f"✅ Puerto {puerto} activo.")
                return True
        sleep(1)
    log(f"❌ Puerto {puerto} no respondió después de {timeout} segundos.")
    return False

# -------------------------------
# EJECUCIÓN PRINCIPAL

try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n==== REINICIO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")
except PermissionError:
    print("⚠️ No se pudo abrir el archivo de log para escritura inicial.")

kill_processes_on_port(8000)
detect_python_cmd()
iniciar_servidor()
esperar_puerto_activo(8000)
