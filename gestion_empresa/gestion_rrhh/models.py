from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal  # Importar Decimal
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
    fecha_entrada = models.DateField(null=True, blank=True)
    fecha_salida= models.DateField(null=True, blank=True)
    dias_vacaciones = models.IntegerField(default=0)
    horas_extra_acumuladas = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Horas extra acumuladas
    horas_compensatorias_disponibles = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Horas compensatorias disponibles
    
    def calcular_dias_vacaciones(self):
        """Calcula los días de vacaciones disponibles según los años trabajados."""
        if not self.fecha_entrada:
            return 0  # Si no hay fecha de entrada registrada, no se puede calcular

        hoy = date.today()
        años_trabajados = hoy.year - self.fecha_entrada.year - ((hoy.month, hoy.day) < (self.fecha_entrada.month, self.fecha_entrada.day))

        # Lógica para los días de vacaciones según los años trabajados
        if años_trabajados < 1:
            return 0  # Menos de un año no tiene días de vacaciones
        elif años_trabajados == 1:
            return 10  # Primer año: 10 días
        elif años_trabajados == 2:
            return 12  # Segundo año: 12 días
        elif años_trabajados == 3:
            return 15  # Tercer año: 15 días
        else:
            return 20  # A partir del cuarto año: 20 días

    def save(self, *args, **kwargs):
        # Actualiza el campo `dias_vacaciones` con el resultado de `calcular_dias_vacaciones`
        self.dias_vacaciones = self.calcular_dias_vacaciones()
        super().save(*args, **kwargs)  # Llama al método `save` del modelo base

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

class RegistroHoras(models.Model):
    TIPOS_HORAS = (
        ('HE', 'Horas Extra'),
        ('HC', 'Horas Compensatorias'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobado'),
        ('R', 'Rechazado'),
    )
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)  # Usuario al que se le registran las horas
    tipo_horas = models.CharField(max_length=2, choices=TIPOS_HORAS)
    fecha_inicio = models.DateTimeField()  # Fecha y hora de inicio
    fecha_fin = models.DateTimeField()  # Fecha y hora de fin
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Horas calculadas
    descripcion = models.TextField(null=True, blank=True)  # Descripción de la actividad
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')  # Estado de aprobación (Pendiente, Aprobado, Rechazado)
    aprobado_por = models.ForeignKey('Usuario', related_name='aprobador_horas', null=True, blank=True, on_delete=models.SET_NULL)  # Jefe que aprueba

    def calcular_horas(self):
        """ Calcula las horas trabajadas a partir de la diferencia entre fecha_inicio y fecha_fin. """
        delta = self.fecha_fin - self.fecha_inicio
        horas = delta.total_seconds() / 3600  # Convierte segundos a horas
        return Decimal(horas).quantize(Decimal('0.01'))  # Convertir a decimal y redondear a dos decimales

    def save(self, *args, **kwargs):
        # Calcular las horas automáticamente antes de guardar
        self.horas = self.calcular_horas()
        super().save(*args, **kwargs)

        # Las horas solo se suman cuando la solicitud es aprobada
        if self.estado == 'A':  # Si la solicitud es aprobada
            if self.tipo_horas == 'HE':
                self.usuario.horas_extra_acumuladas += Decimal(self.horas)
            elif self.tipo_horas == 'HC':
                self.usuario.horas_compensatorias_disponibles += Decimal(self.horas)
            self.usuario.save()
