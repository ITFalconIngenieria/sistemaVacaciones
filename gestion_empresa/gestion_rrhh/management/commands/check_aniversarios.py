from django.core.management.base import BaseCommand
from django.utils import timezone

from gestion_rrhh.models import Usuario


class Command(BaseCommand):
    help = 'Verifica y notifica aniversarios de usuarios'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando verificación de aniversarios...')
        
        hoy = timezone.now().date()
        
        # Buscar usuarios que cumplan años de servicio hoy
        usuarios = Usuario.objects.filter(
            fecha_entrada__month=hoy.month,
            fecha_entrada__day=hoy.day,
            is_active=True,
            fecha_salida__isnull=True  # solo usuarios activos
        )

        for usuario in usuarios:
            self.stdout.write(f'Verificando usuario: {usuario.get_full_name()}')
            usuario.asignar_vacaciones_anuales()
            
        self.stdout.write(self.style.SUCCESS('Verificación de aniversarios completada'))