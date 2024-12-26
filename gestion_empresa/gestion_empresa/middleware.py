from django.http import HttpResponseForbidden
import re

class BlockMiningAttemptsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Patrones comunes de minería
        self.mining_patterns = [
            r'mining\.subscribe',
            r'mining\.authorize',
            r'mining\.submit',
            r'xmr-stak',
            r'stratum\+tcp',
        ]

    def __call__(self, request):
        # Revisar el body de la request
        if hasattr(request, 'body'):
            body = request.body.decode('utf-8', errors='ignore').lower()
            for pattern in self.mining_patterns:
                if re.search(pattern, body):
                    return HttpResponseForbidden('Mining attempts are not allowed')
        
        # Revisar headers sospechosos
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'miner' in user_agent or 'xmr' in user_agent:
            return HttpResponseForbidden('Suspicious user agent detected')

        return self.get_response(request)