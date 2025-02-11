from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date, timedelta
from django.utils.timezone import now, timedelta
from decimal import Decimal
from .validators import validate_username
from django.conf import settings
import random
import string
from django.template.loader import render_to_string
from django.conf import settings
from .utils import MicrosoftGraphEmail 

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
        if not self.fecha_entrada:
            return
            
        hoy = date.today()
        aniversario_actual = date(
            year=hoy.year,
            month=self.fecha_entrada.month,
            day=self.fecha_entrada.day
        )
        
        # Si no es el día exacto del aniversario, no hacemos nada
        if hoy != aniversario_actual:
            return
            
        # Calculamos los años trabajados
        años_trabajados = hoy.year - self.fecha_entrada.year
        
        # Cálculo de días de vacaciones
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

        # Solo creamos el registro en el día del aniversario
        historial, created = HistorialVacaciones.objects.get_or_create(
            usuario=self,
            año=hoy.year,
            defaults={
                'dias_asignados': dias_vacaciones,
                'aniversario_notificado': False
            }
        )
        
        # Enviamos el correo de notificación
        if self.email and not historial.aniversario_notificado:
            context = {
                "nombre_colab": self.get_full_name(),
                "anios_trabajados": años_trabajados,
                'dias_asignados': dias_vacaciones,
            }
            html_content = render_to_string("mail_aniversario.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = f"🎉 ¡FELIZ ANIVERSARIO LABORAL PARA {self.get_full_name()} !🎊"
            
            emails_usuarios = Usuario.objects.filter(
                is_active=True,
                email__isnull=False,
            ).values_list('email', flat=True)
            
            try:
                email_sender.send_email(
                    subject=subject,
                    content=html_content,
                    to_recipients=list(emails_usuarios),
                )
            except Exception as e:
                print(f"Error al enviar correo de aniversario: {e}")
            
            historial.aniversario_notificado = True
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
    descripcion = models.TextField(null=True, blank=True)

    def es_eliminable(self):
        return date.today() <= (self.fecha_inicio.date() + timedelta(days=1))
    
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

    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
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
    aprobado_por = models.ForeignKey('Usuario', related_name='aprobador_horas', null=True, blank=True, on_delete=models.SET_NULL)

    def es_eliminable(self):
        return date.today() <= self.fecha_inicio.date()



class HistorialVacaciones(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    año = models.IntegerField()
    dias_asignados = models.IntegerField(default=0)
    aniversario_notificado = models.BooleanField(default=False)

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
    dias_totales = models.IntegerField(null=True, blank=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='A')
    estado_cierre = models.BooleanField(default=False)

    def es_eliminable(self):
        return date.today() < self.fecha_inicio.date()

    def __str__(self):
        return f"{self.usuario} - {self.get_tipo_display()} ({self.fecha_inicio} a {self.fecha_fin})"



class ConversionVacacionesHoras(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    dias_convertidos = models.DecimalField(max_digits=5, decimal_places=2)
    horas_compensatorias = models.DecimalField(max_digits=6, decimal_places=2)
    fecha_conversion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.dias_convertidos} días -> {self.horas_compensatorias} horas"
    


class HorasCompensatoriasSieteDias(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha_asignacion = models.DateField(auto_now_add=True)
    horas_compensatorias = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    descripcion = models.TextField(default="Horas compensatorias asignadas por trabajar 7 días consecutivos.")

    def __str__(self):
        return f"{self.usuario.get_full_name()} - {self.horas_compensatorias} horas asignadas el {self.fecha_asignacion}"



class CodigoRestablecimiento(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='codigos_restablecimiento')
    codigo = models.CharField(max_length=6, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    usado = models.BooleanField(default=False)

    def es_valido(self):
        fecha_hora_actual = now() - timedelta(hours=6)
        return not self.usado and fecha_hora_actual < self.expira_en