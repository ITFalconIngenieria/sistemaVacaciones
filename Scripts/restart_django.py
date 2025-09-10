import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import psutil
from time import sleep
import socket
import platform

# -------------------------------
# CONFIGURACIONES
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
PROJECT_DIR = PROJECT_ROOT / "gestion_empresa"
LOG_FILE = SCRIPT_DIR / "log_servidor.txt"
PYTHON_CMD = "python"  # por defecto

# -------------------------------
# UTILIDADES DE LOG

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except PermissionError:
        print(f"⚠️ No se pudo escribir en el log (archivo en uso): {msg}")

def _creationflags_no_window() -> int:
    # Evita AttributeError en Linux/macOS
    if platform.system() == "Windows":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0

# -------------------------------
# RED & PROCESOS

def kill_processes_on_port(port: int, timeout_kill: int = 5):
    log(f"🛑 Buscando procesos en el puerto {port}...")

    pids = set()

    # --- Intento 1: una sola llamada global (rápida)
    try:
        for c in psutil.net_connections(kind="inet"):
            # c.laddr puede ser tuple o Address; validamos puerto y estado
            if c.status == psutil.CONN_LISTEN and c.laddr and hasattr(c.laddr, "port") and c.laddr.port == port:
                if c.pid:
                    pids.add(c.pid)
    except Exception as e:
        log(f"⚠️ psutil.net_connections falló o no tiene permisos: {e}")

    # --- Fallback en Windows: netstat -ano | findstr :<port>
    if not pids and platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["cmd", "/c", f"netstat -ano | findstr :{port}"],
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            for line in out.splitlines():
                # Solo líneas en LISTENING, último token es el PID
                if "LISTENING" in line.upper():
                    m = re.findall(r"\s(\d+)\s*$", line)
                    if m:
                        pids.add(int(m[0]))
        except subprocess.CalledProcessError:
            # Código 1 = no encontró coincidencias
            pass
        except Exception as e:
            log(f"⚠️ Fallback netstat falló: {e}")

    if not pids:
        log(f"ℹ️ No había procesos escuchando en el puerto {port}.")
        sleep(1)
        return

    # --- Matar PIDs encontrados
    for pid in pids:
        try:
            log(f"Matando proceso PID {pid} que usaba el puerto {port}")
            p = psutil.Process(pid)
            p.kill()
            try:
                p.wait(timeout=timeout_kill)
            except psutil.TimeoutExpired:
                log(f"⏳ PID {pid} no terminó con kill(); intentando terminate()")
                p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            log(f"⚠️ No se pudo terminar PID {pid}: {e}")

    sleep(1)


def esperar_puerto_activo(puerto: int, timeout: int = 20) -> bool:
    log(f"⏳ Esperando a que el puerto {puerto} esté activo (timeout {timeout}s)...")
    for _ in range(timeout):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", puerto)) == 0:
                log(f"✅ Puerto {puerto} activo.")
                return True
        sleep(1)
    log(f"❌ Puerto {puerto} no respondió después de {timeout} segundos.")
    return False

# -------------------------------
# PYTHON / ENTORNO

def detect_python_cmd():
    """
    - Si hay venv en Windows: <root>/venv/Scripts/python.exe o pythonw.exe
    - Si hay venv en Unix:    <root>/venv/bin/python
    - Si no, deja 'python' (sistema) y loguea aviso.
    """
    global PYTHON_CMD

    # Windows
    for exe_name in ("pythonw.exe", "python.exe"):
        candidate = PROJECT_ROOT / "venv" / "Scripts" / exe_name
        if candidate.exists():
            PYTHON_CMD = str(candidate)
            log(f"✅ Entorno virtual detectado (Windows): {PYTHON_CMD}")
            return

    # Unix
    candidate = PROJECT_ROOT / "venv" / "bin" / "python"
    if candidate.exists():
        PYTHON_CMD = str(candidate)
        log(f"✅ Entorno virtual detectado (Unix): {PYTHON_CMD}")
        return

    log("⚠️ No se encontró entorno virtual. Se usará Python del sistema (python).")

# -------------------------------
# LANZAR SERVIDOR SSL (SIEMPRE)

def iniciar_servidor_ssl(puerto: int = 8000, timeout: int = 20) -> bool:
    """
    Lanza SIEMPRE 'runsslserver' en 0.0.0.0:<puerto>.
    - Mata procesos previos en ese puerto.
    - Espera a que el puerto quede activo.
    - Si no queda activo, termina el proceso lanzado y devuelve False.
    """
    if not PROJECT_DIR.exists():
        log(f"❌ No se encontró el directorio del proyecto: {PROJECT_DIR}")
        return False

    manage_py = PROJECT_DIR / "manage.py"
    if not manage_py.exists():
        log(f"❌ No se encontró manage.py en: {PROJECT_DIR}")
        return False

    os.chdir(PROJECT_DIR)
    log(f"🚀 Iniciando servidor Django con runsslserver en 0.0.0.0:{puerto}...")

    proc = None
    try:
        log_file = open(LOG_FILE, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [PYTHON_CMD, "manage.py", "runsslserver", f"0.0.0.0:{puerto}"],
            stdout=log_file,
            stderr=log_file,
            cwd=PROJECT_DIR,
            creationflags=_creationflags_no_window()
        )

        if esperar_puerto_activo(puerto, timeout=timeout):
            log("✅ Servidor SSL lanzado correctamente.")
            return True
        else:
            log("❌ runsslserver no activó el puerto dentro del tiempo esperado.")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception as e:
                log(f"⚠️ Error al cerrar proceso fallido: {e}")
            return False

    except FileNotFoundError as e:
        log(f"❌ No se encontró ejecutable/comando: {e}")
        return False
    except Exception as e:
        log(f"❌ Error al iniciar runsslserver: {str(e)}")
        return False

# -------------------------------
# EJECUCIÓN PRINCIPAL

if __name__ == "__main__":
    # Separador de reinicio en el log
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n==== REINICIO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    except PermissionError:
        print("⚠️ No se pudo abrir el archivo de log para escritura inicial.")

    # 1) Cerrar cualquier proceso que esté usando el puerto 8000
    kill_processes_on_port(8000)

    # 2) Detectar python del venv (si existe)
    detect_python_cmd()

    # 3) Iniciar SIEMPRE runsslserver
    ok = iniciar_servidor_ssl(puerto=8000, timeout=20)

    # 4) Código de salida útil para orquestadores/servicios externos
    if not ok:
        log("⛔ Finalizando con código 1 porque runsslserver no quedó activo.")
        sys.exit(1)
    else:
        # Nota: el proceso de Django queda en marcha en segundo plano;
        # este script puede terminar aquí sin matar al servidor.
        sys.exit(0)
