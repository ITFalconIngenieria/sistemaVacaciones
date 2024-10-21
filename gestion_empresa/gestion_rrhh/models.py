from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError

class Usuario(AbstractUser):
    ROLES = (
        ('GG', 'Gerente General'),
        ('JI', 'Jefe de Ingenieros'),
        ('JD', 'Jefe de Departamento'),
        ('IN', 'Ingeniero'),
        ('TE', 'Técnico'),
    )
    rol = models.CharField(max_length=2, choices=ROLES)
    departamento = models.ForeignKey('Departamento', on_delete=models.SET_NULL, null=True)
    jefe = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='subordinados')

class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre

class Solicitud(models.Model):
    TIPOS = (
        ('V', 'Vacaciones'),
        ('HE', 'Horas Extra'),
        ('HC', 'Horas Compensatorias'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=2, choices=TIPOS)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')
    aprobado_por = models.ForeignKey(Usuario, related_name='aprobador', null=True, blank=True, on_delete=models.SET_NULL)
    
    def clean(self):
        super().clean()
        if self.tipo == 'HE' and self.usuario.rol == 'IN':
            raise ValidationError("Los ingenieros no pueden solicitar horas extra.")
        
        if self.estado != 'P' and self.aprobado_por == self.usuario:
            raise ValidationError("No puedes aprobar tu propia solicitud.")
        
        if self.tipo == 'HC' and self.usuario.rol == 'TE':
            horas_extra = Solicitud.objects.filter(
                usuario=self.usuario,
                tipo='HE',
                estado='A'
            ).aggregate(total=models.Sum('horas'))['total'] or 0
            
            if self.horas > horas_extra:
                raise ValidationError("No tienes suficientes horas extra para convertir en compensatorias.")

    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Convertir horas extra a compensatorias para técnicos
        if self.tipo == 'HC' and self.estado == 'A' and self.usuario.rol == 'TE':
            horas_extra = Solicitud.objects.filter(
                usuario=self.usuario,
                tipo='HE',
                estado='A'
            ).order_by('fecha_inicio')
            
            horas_restantes = self.horas
            for solicitud_he in horas_extra:
                if horas_restantes <= 0:
                    break
                if solicitud_he.horas <= horas_restantes:
                    solicitud_he.estado = 'R'  # Marcar como usada
                    horas_restantes -= solicitud_he.horas
                else:
                    solicitud_he.horas -= horas_restantes
                    horas_restantes = 0
                solicitud_he.save()