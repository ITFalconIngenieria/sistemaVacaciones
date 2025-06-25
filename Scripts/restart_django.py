import subprocess
import os
import signal
import time
import logging
from datetime import datetime

def setup_logging():
    """Configura el sistema de logging"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'django_server.log')
    
    # Configurar logging para archivo y consola
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Para mostrar en consola también
        ]
    )
    
    return logging.getLogger(__name__)

def log_and_print(logger, message, level='info'):
    """Función helper para imprimir y loggear al mismo tiempo"""
    print(message)
    if level == 'info':
        logger.info(message.replace('🔄', '').replace('✅', '').replace('⚠️', '').replace('❌', '').replace('🛑', '').replace('📁', '').replace('🚀', '').replace('⏹️', '').strip())
    elif level == 'error':
        logger.error(message.replace('❌', '').strip())
    elif level == 'warning':
        logger.warning(message.replace('⚠️', '').strip())

def find_project_root():
    """Encuentra la raíz del proyecto automáticamente"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Si estamos en Scripts, buscar gestion_empresa en el nivel superior
    if os.path.basename(current_dir) == 'Scripts':
        parent_dir = os.path.dirname(current_dir)
        gestion_path = os.path.join(parent_dir, 'gestion_empresa')
        if os.path.exists(os.path.join(gestion_path, 'manage.py')):
            return gestion_path
    
    # Buscar en otras ubicaciones posibles
    search_paths = [
        os.path.join(current_dir, '..', 'gestion_empresa'),
        os.path.join(current_dir, 'gestion_empresa'),
        current_dir
    ]
    
    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(os.path.join(abs_path, 'manage.py')):
            return abs_path
    
    return None

def find_python_executable():
    """Encuentra el ejecutable de Python (virtual env o sistema)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) if os.path.basename(current_dir) == 'Scripts' else current_dir
    
    # Buscar entornos virtuales comunes
    venv_paths = [
        os.path.join(project_root, 'venv', 'Scripts', 'python.exe'),
        os.path.join(project_root, 'env', 'Scripts', 'python.exe'),
        os.path.join(project_root, '.venv', 'Scripts', 'python.exe'),
        os.path.join(project_root, 'virtualenv', 'Scripts', 'python.exe')
    ]
    
    for venv_path in venv_paths:
        if os.path.exists(venv_path):
            venv_name = os.path.basename(os.path.dirname(os.path.dirname(venv_path)))
            return venv_path, venv_name
    
    return 'python', 'sistema'

# Configuración automática
logger = setup_logging()
PROJECT_PATH = find_project_root()
PYTHON_CMD, VENV_TYPE = find_python_executable()
HOST = "0.0.0.0"
PORT = "8000"

def kill_process_on_port(port):
    """Mata el proceso que está usando el puerto especificado"""
    try:
        # Buscar proceso en el puerto
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            if f':{port}' in line and 'LISTENING' in line:
                # Extraer PID
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    print(f"Matando proceso en puerto {port} (PID: {pid})")
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                    return True
        return False
    except Exception as e:
        print(f"Error al matar proceso en puerto {port}: {e}")
        return False

def restart_django():
    """Reinicia el servidor Django"""
    print("🔄 Reiniciando servidor Django...")
    
    # Verificar que encontramos el proyecto
    if not PROJECT_PATH:
        print("❌ Error: No se pudo encontrar el proyecto Django (manage.py)")
        return
    
    # 1. Matar proceso en puerto 8000
    print("🛑 Deteniendo servidor existente...")
    kill_process_on_port(PORT)
    
    # 2. Esperar un momento
    time.sleep(2)
    
    # 3. Cambiar al directorio del proyecto
    os.chdir(PROJECT_PATH)
    print(f"📁 Directorio: {PROJECT_PATH}")
    
    # 4. Iniciar servidor
    print(f"🚀 Iniciando servidor en {HOST}:{PORT}...")
    try:
        subprocess.run([PYTHON_CMD, 'manage.py', 'runsslserver', f'{HOST}:{PORT}'])
    except KeyboardInterrupt:
        print("\n⏹️  Servidor detenido por el usuario")

if __name__ == "__main__":
    restart_django()