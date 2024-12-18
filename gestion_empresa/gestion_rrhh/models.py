from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date, timedelta, datetime, time
from decimal import Decimal
from .validators import validate_username
from django.conf import settings
import random
import string
from django.template.loader import render_to_string
from django.conf import settings
from .utils import MicrosoftGraphEmail 


from dateutil.relativedelta import relativedelta
class Usuario(AbstractUser):
    recalcular_vacaciones = True
    ROLES = (
        ('GG', 'Gerente General'),
        ('JI', 'Jefe de Ingenieros'),
        ('JD', 'Jefe de Departamento'),
        ('IN', 'Ingeniero'),
        ('TE', 'Técnico'),
        ('AST', 'Asistente'),
        ('FNZ', 'Finanzas'),
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[validate_username],
        help_text="Solo letras, sin números ni caracteres especiales."
    )
    rol = models.CharField(max_length=3, choices=ROLES)
    departamento = models.ForeignKey('Departamento', on_delete=models.SET_NULL, null=True)
    jefe = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='subordinados')
    fecha_entrada = models.DateField(null=True, blank=True)
    fecha_salida= models.DateField(null=True, blank=True)
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
        
        historial, created = HistorialVacaciones.objects.get_or_create(usuario=self, año=año_actual)
        if created:
            historial.dias_asignados = dias_vacaciones
            historial.save()

    def _generate_random_password(self, length=10):
        characters = string.ascii_letters + string.digits + "!@#$%^&*()"
        if not characters or length <= 0:
            print("Error: Lista de caracteres vacía o longitud inválida.")
            return None

        password = ''.join(random.choices(characters, k=length)) 
        return password


    
    def send_welcome_email(self, plain_password):
        if self.email:

            context = {
                "nombre_usuario": self.first_name,
                "username": self.username,
                "password": plain_password,
                "url_sistema": settings.ENLACE_DEV,
            }

            html_content = render_to_string("mail_bienvenida.html", context)

            email_sender = MicrosoftGraphEmail()
            subject = "Bienvenido a la plataforma"
            content = html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[self.email],
                )
            except Exception as e:
                print(f"Error al enviar correo de bienvenida a {self.email}: {e}")

    def save(self, *args, **kwargs):
        is_new = not self.pk
        plain_password = None

        if is_new:
            if self.email:
                self.username = self.email.split('@')[0]
            
            if not self.password:
                plain_password = self._generate_random_password()
                self.set_password(plain_password)

        super().save(*args, **kwargs)

        if is_new and plain_password:
            self.send_welcome_email(plain_password)
        elif is_new:
            print("Error: No se generó la contraseña para enviar el correo.")

        self.asignar_vacaciones_anuales()


class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre


class Solicitud(models.Model):
    TIPOS = (
        ('V', 'Solicitud Vacaciones'),
        ('HC', 'Solicitud Horas Compensatorias'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    numero_solicitud=models.CharField(max_length=50,unique=True, blank=True)
    tipo = models.CharField(max_length=2, choices=TIPOS)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    dias_solicitados = models.IntegerField(null=True, blank=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')
    aprobado_por = models.ForeignKey(Usuario, related_name='aprobador', null=True, blank=True, on_delete=models.SET_NULL)
    estado_cierre = models.BooleanField(default=False)
    requisitos_confirmados = models.BooleanField(default=False)

    def es_eliminable(self):
        return date.today() <= self.fecha_inicio.date()
    
    def save(self, *args, **kwargs):
        if self.tipo == 'V':
            self.fecha_inicio = self.fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
            self.fecha_fin = self.fecha_fin.replace(hour=0, minute=0, second=0, microsecond=0)
        self.full_clean()
        super().save(*args, **kwargs)


class RegistroHoras(models.Model):
    TIPOS_HORAS = (
        ('HE', 'Registro Horas Extras'),
        ('HC', 'Registro Horas Compensatorias'),
        ('HEF', 'Registro Horas Dia Feriado'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobado'),
        ('R', 'Rechazado'),
    )
    ESTADOS_PAGO = (
        ('NP', 'No Pagado'),
        ('PG', 'Pagado'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=3, choices=TIPOS_HORAS)
    numero_registro = models.CharField(max_length=50, unique=True, blank=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField() 
    horas = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    horas_compensatorias_feriado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    numero_proyecto = models.IntegerField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True) 
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P') 
    estado_pago = models.CharField(max_length=2, choices=ESTADOS_PAGO, default='NP')
    aprobado_por = models.ForeignKey(Usuario, related_name='aprobador_horas', null=True, blank=True, on_delete=models.SET_NULL)
    
    def es_eliminable(self):
        return date.today() <= self.fecha_inicio.date()


    def calcular_horas(self):
        feriados = FeriadoNacional.objects.values_list('fecha', flat=True)

        
        delta = self.fecha_fin - self.fecha_inicio
        total_horas = delta.total_seconds() / 3600

        almuerzo_inicio = self.fecha_inicio.replace(hour=12, minute=0, second=0, microsecond=0)
        almuerzo_fin = self.fecha_inicio.replace(hour=13, minute=0, second=0, microsecond=0)

        es_dia_especial = (
            self.fecha_inicio.date() in feriados or
            self.fecha_inicio.weekday() >= 5
        )

        # Solo restar hora de almuerzo si NO es un día especial
        if not es_dia_especial:
            if self.fecha_inicio <= almuerzo_inicio < self.fecha_fin or self.fecha_inicio < almuerzo_fin <= self.fecha_fin:
                total_horas -= 1 

        total_horas = max(total_horas, 0) 
        return Decimal(total_horas).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        self.horas = self.calcular_horas()
        if self.tipo == 'HC' and self.fecha_inicio.weekday() == 6 and self.fecha_fin.weekday() == 6:
            self.horas *= 2

        if self.tipo == 'HEF':
            diferencia_dias = (self.fecha_fin.date() - self.fecha_inicio.date()).days + 1
            self.horas_compensatorias_feriado = 9 * diferencia_dias
        super().save(*args, **kwargs)

class HistorialVacaciones(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    año = models.IntegerField()
    dias_asignados = models.IntegerField(default=0)
    dias_tomados = models.IntegerField(default=0)

    class Meta:
        unique_together = ('usuario', 'año')

class AjusteVacaciones(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    año = models.IntegerField()
    dias_ajustados = models.IntegerField(default=0)
    descripcion = models.TextField(null=True, blank=True)
    fecha_ajuste = models.DateField(auto_now_add=True)
    ajustado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='ajustes_realizados')

    def __str__(self):
        return f"Ajuste de {self.dias_ajustados} días para {self.usuario} en el año {self.año}"


class Incapacidad(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='incapacidades'
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    archivo_adjunto = models.FileField(
        upload_to='incapacidades/',
        blank=False,
        null=False
    )
    descripcion = models.TextField(blank=True, null=True)
    dias_incapacidad = models.IntegerField(default=0)
    revisado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def es_eliminable(self):
        return date.today() == self.fecha_inicio and self.revisado==0

    def save(self, *args, **kwargs):
        if self.fecha_inicio and self.fecha_fin:
            self.dias_incapacidad = (self.fecha_fin - self.fecha_inicio).days + 1
        else:
            self.dias_incapacidad = 0
        super().save(*args, **kwargs)  
    def __str__(self):
        return f"Incapacidad de {self.usuario.get_full_name()} del {self.fecha_inicio} al {self.fecha_fin}"


class FeriadoNacional(models.Model):
    fecha = models.DateField(unique=True, verbose_name="Fecha del Feriado")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")

    class Meta:
        verbose_name = "Feriado Nacional"
        verbose_name_plural = "Feriados Nacionales"
        ordering = ['fecha']

    def __str__(self):
        return f"{self.fecha} - {self.descripcion}"
    



class Licencia(models.Model):
    TIPOS = (
        ('LAC', 'Lactancia'),
        ('MAT', 'Matrimonio'),
        ('CAL', 'Calamidad Doméstica'),
    )
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=3, choices=TIPOS)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    horas_totales = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    dias_totales = models.IntegerField(null=True, blank=True)  # Para almacenar los días en Matrimonio
    estado = models.CharField(max_length=1, choices=ESTADOS, default='P')

    def es_feriado(self, fecha):
        return FeriadoNacional.objects.filter(fecha=fecha).exists()

    def calcular_fecha_lactancia(self):
        fecha_final = self.fecha_inicio + relativedelta(months=6)
        fecha_final = fecha_final.replace(hour=self.fecha_inicio.hour + 1, minute=0, second=0)
        return fecha_final

    def calcular_fecha_matrimonio(self):
        fecha_actual = self.fecha_inicio.date()
        total_dias = 0

        while total_dias < 3:
            if fecha_actual.weekday() < 5 and not self.es_feriado(fecha_actual):
                total_dias += 1
                if total_dias == 3:
                    break
            fecha_actual += timedelta(days=1)

        return datetime.combine(fecha_actual, time(0, 0, 0))


    def calcular_horas_calamidad(self):
        almuerzo_inicio = self.fecha_inicio.replace(hour=12, minute=0, second=0)
        almuerzo_fin = self.fecha_inicio.replace(hour=13, minute=0, second=0)
        delta = self.fecha_fin - self.fecha_inicio
        total_horas = delta.total_seconds() / 3600

        if self.fecha_inicio < almuerzo_fin and self.fecha_fin > almuerzo_inicio:
            total_horas -= 1 
        return total_horas

    def es_eliminable(self):
        return date.today() < self.fecha_inicio.date()

    def save(self, *args, **kwargs):
        if self.tipo == 'LAC': 
            self.fecha_fin = self.calcular_fecha_lactancia()
            self.horas_totales = 1
        elif self.tipo == 'MAT':
            self.fecha_inicio = datetime.combine(self.fecha_inicio.date(), time(0, 0, 0))
            self.fecha_fin = self.calcular_fecha_matrimonio()
            self.dias_totales = 3
        elif self.tipo == 'CAL':
            self.horas_totales = self.calcular_horas_calamidad()
            # Validar las horas acumuladas en el año
            horas_acumuladas = Licencia.objects.filter(
                usuario=self.usuario,
                tipo='CAL',
                fecha_inicio__year=self.fecha_inicio.year
            ).exclude(pk=self.pk).aggregate(models.Sum('horas_totales'))['horas_totales__sum'] or 0

            if horas_acumuladas + self.horas_totales > 135:
                raise ValueError("No se pueden registrar más de 135 horas para Calamidad Doméstica en el año.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario} - {self.get_tipo_display()} ({self.fecha_inicio} a {self.fecha_fin})"

