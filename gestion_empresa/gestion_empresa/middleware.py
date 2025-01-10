from django.http import HttpResponseForbidden
import re
import json
from django.core.cache import cache
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Mining patterns
        self.mining_patterns = [
            r'mining\.subscribe',
            r'mining\.authorize',
            r'mining\.submit',
            r'xmr-stak',
            r'stratum\+tcp',
            r'xmrig',
            r'cryptonight',
            r'monero',
            r'eth_submitLogin',
            r'eth_getWork',
            r'hashrate',
            r'minergate',
            r'antminer',
        ]
        
        # Suspicious user agents
        self.suspicious_agents = [
            'miner',
            'xmr',
            'minergate',
            'nicehash',
            'bfgminer',
            'cgminer',
            'ccminer',
            'claymore',
            'phoenixminer',
        ]
        
        # Rate limiting settings
        self.max_requests = getattr(settings, 'SECURITY_MAX_REQUESTS', 50)
        self.window_seconds = getattr(settings, 'SECURITY_WINDOW_SECONDS', 60)
        
        # Allowed hosts from settings
        self.allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])

    def log_attack(self, request, attack_type):
        ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        timestamp = datetime.now().isoformat()
        
        logger.warning(f"Security alert - {attack_type} - IP: {ip} - UA: {user_agent} - Time: {timestamp}")

    def is_rate_limited(self, ip):
        key = f'rate_limit_{ip}'
        requests = cache.get(key, 0)
        
        if requests >= self.max_requests:
            return True
            
        cache.set(key, requests + 1, self.window_seconds)
        return False

    def check_json_payload(self, body):
        try:
            data = json.loads(body)
            suspicious_fields = ['algo', 'wallet', 'pool', 'hashrate', 'worker', 'difficulty']
            return any(field in str(data).lower() for field in suspicious_fields)
        except json.JSONDecodeError:
            return False

    def check_host(self, request):
        host = request.get_host().split(':')[0]
        return host in self.allowed_hosts

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        
        # Host validation
        if not self.check_host(request):
            self.log_attack(request, "Invalid host")
            return HttpResponseForbidden('Invalid host')

        # Rate limiting
        if self.is_rate_limited(ip):
            self.log_attack(request, "Rate limit exceeded")
            return HttpResponseForbidden('Too many requests')

        # Body checks
        if hasattr(request, 'body'):
            try:
                body = request.body.decode('utf-8', errors='ignore').lower()
                
                # Mining patterns check
                for pattern in self.mining_patterns:
                    if re.search(pattern, body):
                        self.log_attack(request, "Mining pattern detected")
                        return HttpResponseForbidden('Mining attempts not allowed')
                
                # JSON payload check
                if self.check_json_payload(body):
                    self.log_attack(request, "Suspicious JSON payload")
                    return HttpResponseForbidden('Suspicious payload detected')
                    
            except UnicodeDecodeError:
                self.log_attack(request, "Invalid request encoding")
                return HttpResponseForbidden('Invalid request encoding')

        # User agent check
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if any(agent in user_agent for agent in self.suspicious_agents):
            self.log_attack(request, "Suspicious user agent")
            return HttpResponseForbidden('Suspicious user agent')

        # Suspicious headers check
        headers = request.META
        suspicious_headers = ['x-mining-extensions', 'x-mining-proxy', 'x-pool-address']
        if any(header in headers for header in suspicious_headers):
            self.log_attack(request, "Suspicious headers")
            return HttpResponseForbidden('Suspicious headers detected')

        return self.get_response(request)