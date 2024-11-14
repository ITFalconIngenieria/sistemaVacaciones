from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date
from decimal import Decimal  # Importar Decimal
from django.contrib.auth import get_user_model
from .validators import validate_username



class Usuario(AbstractUser):
    recalcular_vacaciones = True
    ROLES = (
        ('GG', 'Gerente General'),
        ('JI', 'Jefe de Ingenieros'),
        ('JD', 'Jefe de Departamento'),
        ('IN', 'Ingeniero'),
        ('TE', 'Técnico'),
    )
    # Aplicar el validador personalizado al campo `username`
    username = models.CharField(
        max_length=150,
        unique=True,  # Mantener la unicidad
        validators=[validate_username],  # Agregar el validador de solo letras
        help_text="Solo letras, sin números ni caracteres especiales."
    )
    rol = models.CharField(max_length=2, choices=ROLES)
    departamento = models.ForeignKey('Departamento', on_delete=models.SET_NULL, null=True)
    jefe = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='subordinados')
    fecha_entrada = models.DateField(null=True, blank=True)
    fecha_salida= models.DateField(null=True, blank=True)
    horas_extra_acumuladas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    horas_compensatorias_disponibles = models.DecimalField(max_digits=5, decimal_places=2, default=0)  
    mostrar_en_dashboard = models.BooleanField(default=True, help_text="Determina si el usuario aparecerá en el dashboard.")
    
    def asignar_vacaciones_anuales(self):
        """Asigna días de vacaciones al usuario según los años trabajados."""
        if not self.fecha_entrada:
            return
        
        hoy = date.today()
        año_actual = hoy.year
        años_trabajados = hoy.year - self.fecha_entrada.year - ((hoy.month, hoy.day) < (self.fecha_entrada.month, self.fecha_entrada.day))

        dias_vacaciones = 0
        if años_trabajados < 1:
            dias_vacaciones = 0
        elif años_trabajados == 1:
            dias_vacaciones = 10
        elif años_trabajados == 2:
            dias_vacaciones = 12
        elif años_trabajados == 3:
            dias_vacaciones = 15
        else:
            dias_vacaciones = 20
        
        # Obtener o crear el registro de vacaciones para el año actual
        historial, created = HistorialVacaciones.objects.get_or_create(usuario=self, año=año_actual)
        if created:
            historial.dias_asignados = dias_vacaciones
            historial.save()

    def save(self, *args, **kwargs):
        """Override save to assign vacations automatically each year."""
        self.asignar_vacaciones_anuales()
        super().save(*args, **kwargs)


class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre


class Solicitud(models.Model):
    TIPOS = (
        ('V', 'Solicitud Vacaciones'),
        # ('HE', 'Horas Extra'),
        ('HC', 'Solicitud Horas Compensatorias'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    numero_solicitud=models.CharField(max_length=10,unique=True, blank=True)
    tipo = models.CharField(max_length=2, choices=TIPOS)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    dias_solicitados = models.IntegerField(null=True, blank=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')
    aprobado_por = models.ForeignKey(Usuario, related_name='aprobador', null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class RegistroHoras(models.Model):
    TIPOS_HORAS = (
        ('HE', 'Registro Horas Extra'),
        ('HC', 'Registro Horas Compensatorias'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobado'),
        ('R', 'Rechazado'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)  # Usuario al que se le registran las horas
    tipo = models.CharField(max_length=2, choices=TIPOS_HORAS)
    numero_registro = models.CharField(max_length=10,unique=True, blank=True)  # Número de registro personalizado
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField() 
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) 
    numero_proyecto=models.IntegerField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True) 
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P') 
    aprobado_por = models.ForeignKey(Usuario, related_name='aprobador_horas', null=True, blank=True, on_delete=models.SET_NULL)
   
    def calcular_horas(self):
        """ Calcula las horas trabajadas a partir de la diferencia entre fecha_inicio y fecha_fin. """
        delta = self.fecha_fin - self.fecha_inicio
        horas = delta.total_seconds() / 3600  # Convierte segundos a horas
        return Decimal(horas).quantize(Decimal('0.01'))  # Convertir a decimal y redondear a dos decimales

    def save(self, *args, **kwargs):
        # Calcular las horas automáticamente antes de guardar
        self.horas = self.calcular_horas()
         # Multiplicar horas por 2 si es domingo y el tipo es compensatorias (HC)
        if self.tipo == 'HC' and self.fecha_inicio.weekday() == 6 and self.fecha_fin.weekday()== 6:  # 6 representa domingo en Python
            self.horas *= 2

            
        super().save(*args, **kwargs)


# class HistorialVacaciones(models.Model):
#     usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
#     año = models.IntegerField()
#     dias_asignados = models.IntegerField(default=0)
#     dias_tomados = models.IntegerField(default=0)

#     class Meta:
#         unique_together = ('usuario', 'año')

#     def dias_disponibles(self):
#         """Retorna los días de vacaciones disponibles."""
#         return self.dias_asignados - self.dias_tomados



class HistorialVacaciones(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    año = models.IntegerField()
    dias_asignados = models.IntegerField(default=0)
    dias_tomados = models.IntegerField(default=0)

    class Meta:
        unique_together = ('usuario', 'año')

    def dias_disponibles(self):
        """Retorna los días de vacaciones disponibles en este registro, incluyendo ajustes."""
        dias_sin_ajustes = self.dias_asignados - self.dias_tomados
        ajuste_vacaciones = AjusteVacaciones.objects.filter(usuario=self.usuario).aggregate(
            total_ajuste=models.Sum('dias_ajustados')
        )['total_ajuste'] or 0

        return dias_sin_ajustes + ajuste_vacaciones

    @classmethod
    def calcular_dias_disponibles_totales(cls, usuario):
        """Calcula el total de días de vacaciones disponibles para el usuario considerando todos los años."""
        historial = cls.objects.filter(usuario=usuario)
        total_dias_disponibles = sum(item.dias_disponibles() for item in historial)
        return total_dias_disponibles



class AjusteVacaciones(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    año = models.IntegerField()  # Agrega este campo
    dias_ajustados = models.IntegerField(default=0)
    descripcion = models.TextField(null=True, blank=True)
    fecha_ajuste = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Ajuste de {self.dias_ajustados} días para {self.usuario} en el año {self.año}"
