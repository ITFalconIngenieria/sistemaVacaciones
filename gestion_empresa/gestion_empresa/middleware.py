from django.http import HttpResponseForbidden
import os
import logging
import re
from django.core.cache import cache

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.banned_ips_file = "banned_ips.txt"  # Archivo donde se guardan las IPs bloqueadas permanentemente
        self.blocked_ips = self.load_blocked_ips()  # Cargar IPs bloqueadas al iniciar

        # ✅ Lista de IPs permitidas siempre (whitelist)
        self.allowed_ips = {"190.4.48.82"}

        # 🚫 Bloqueo de User-Agent sospechosos
        self.blocked_user_agents = [
            "curl", "wget", "python-requests", "nmap", "sqlmap", "fuzz", "masscan"
        ]

        # 🚫 Bloqueo de intentos de acceso a archivos sensibles
        self.blocked_paths = [
            ".env", "phpinfo.php", "config.json", "debug", "awsconfig.json",
            "database.yml", "credentials", "setup.php", "server-status"
        ]

        # 🚫 Bloqueo de headers sospechosos usados en ataques automatizados
        self.blocked_headers = [
            "x-mining-extensions", "x-mining-proxy", "x-pool-address",
            "x-forwarded-for", "x-originating-ip"
        ]

        # 🔥 Rate Limiting (Si una IP hace más de 50 requests en 60s, la bloquea para siempre)
        self.max_requests = 50
        self.window_seconds = 60

    def load_blocked_ips(self):
        """ Carga la lista de IPs bloqueadas desde el archivo y las guarda en memoria. """
        if os.path.exists(self.banned_ips_file):
            with open(self.banned_ips_file, "r") as file:
                return set(file.read().splitlines())
        return set()

    def save_blocked_ip(self, ip):
        """ Agrega una IP a la lista de bloqueadas permanentemente y la guarda en el archivo. """
        if ip not in self.blocked_ips:
            self.blocked_ips.add(ip)
            with open(self.banned_ips_file, "a") as file:
                file.write(ip + "\n")
            logger.warning(f"🔴 Permanently blocked IP: {ip}")

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path.lower()

        # ✅ 0. Permitir siempre las IPs en la lista blanca
        if ip in self.allowed_ips:
            return self.get_response(request)

        # 🚫 1. Bloqueo de IPs Maliciosas (guardadas en archivo)
        if ip in self.blocked_ips:
            logger.warning(f"⛔ Blocked attempt from {ip}")
            return HttpResponseForbidden("Access Denied")

        # 🚫 2. Bloqueo de User-Agents de Bots
        if any(agent in user_agent for agent in self.blocked_user_agents):
            self.save_blocked_ip(ip)  # Guardar IP en archivo
            return HttpResponseForbidden("Bot detected")

        # 🚫 3. Bloqueo de Acceso a Archivos Sensibles
        if any(path.endswith(p) for p in self.blocked_paths):
            self.save_blocked_ip(ip)  # Guardar IP en archivo
            return HttpResponseForbidden("Access Denied")

        # 🚫 4. Bloqueo de Headers Sospechosos
        for header in self.blocked_headers:
            if header in request.META:
                self.save_blocked_ip(ip)  # Guardar IP en archivo
                return HttpResponseForbidden("Suspicious Request Detected")

        # 🔥 5. Rate Limiting: Bloqueo Definitivo tras Excesivas Solicitudes
        if self.is_rate_limited(ip):
            self.save_blocked_ip(ip)  # Guardar IP en archivo
            return HttpResponseForbidden("Too Many Requests")

        return self.get_response(request)

    def is_rate_limited(self, ip):
        """ Bloquea IPs con más de 50 requests en 60 segundos PERMANENTEMENTE. """
        key = f"rate_limit_{ip}"
        attempts = cache.get(key, 0)

        if attempts >= self.max_requests:
            return True

        cache.set(key, attempts + 1, self.window_seconds)
        return False
