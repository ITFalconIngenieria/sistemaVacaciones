# gestion_rrhh/validators.py
from django.core.exceptions import ValidationError
import re

def validate_username(value):
    # Solo permitir letras (sin números ni caracteres especiales)
    if not re.match(r'^[a-zA-Z]+$', value):
        raise ValidationError('El nombre de usuario solo debe contener letras (sin números ni caracteres especiales).')
