from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View, DeleteView
from .models import FeriadoNacional, Usuario, Solicitud, HistorialVacaciones, ConversionVacacionesHoras, AjusteVacaciones, RegistroHoras,Solicitud, Incapacidad 
from .forms import UsuarioCreationForm, SolicitudForm, FeriadoNacionalForm, RegistrarHorasForm,RegistroHorasFilterForm, AjusteVacacionesForm, IncapacidadForm
from django.contrib import messages
from django.contrib.auth import logout
from operator import attrgetter
from django.core.paginator import Paginator
from datetime import date
from django.db.models import Sum , Q
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import timezone
import locale
from django.contrib.auth.views import PasswordChangeView
from django.utils.timezone import now, timedelta
import json
from django.core.exceptions import PermissionDenied
from .utils import MicrosoftGraphEmail
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.conf import settings
from datetime import datetime, time
from django.utils.timezone import make_aware , get_current_timezone
from django.http import JsonResponse
import uuid
import pytz
from .models import Licencia
from .forms import LicenciaForm
from django.db import models
from dateutil.relativedelta import relativedelta
from decimal import Decimal


def es_jefe(user):
    return user.rol in ['GG', 'JI', 'JD']

def calcular_dias_disponibles(usuario):
    total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
    total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
    total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
    total_dias_convertidos = ConversionVacacionesHoras.objects.filter(usuario=usuario).aggregate(Sum('dias_convertidos'))['dias_convertidos__sum'] or 0

    dias_disponibles = total_dias_asignados + total_dias_ajustados - total_dias_tomados - total_dias_convertidos
    return {
        'total_asignados': total_dias_asignados,
        'total_tomados': total_dias_tomados,
        'total_ajustados': total_dias_ajustados,
        'total_convertidos': total_dias_convertidos,
        'dias_disponibles': dias_disponibles
    }


# def calcular_horas_individuales(usuario):
#     tipos = ['HE', 'HC'] 
#     horas_por_tipo = {'HE': 0, 'HC': 0}
#     for tipo in tipos:
#         total_horas = RegistroHoras.objects.filter(
#             usuario=usuario,
#             tipo=tipo,
#             estado='A',
#             estado_pago='NP'
#         ).aggregate(Sum('horas'))['horas__sum'] or 0
#         horas_por_tipo[tipo] = total_horas
#     horas_hef = RegistroHoras.objects.filter(
#         usuario=usuario,
#         tipo='HEF',
#         estado='A',
#         estado_pago='NP'  
#     ).aggregate(
#         total_horas=Sum('horas'),
#         horas_compensatorias_feriado=Sum('horas_compensatorias_feriado')
#     )
#     horas_por_tipo['HE'] += horas_hef['total_horas'] or 0
#     horas_por_tipo['HC'] += horas_hef['horas_compensatorias_feriado'] or 0
#     horas_solicitudes_hc = Solicitud.objects.filter(
#         usuario=usuario,
#         tipo='HC',
#         estado='A'
#     ).aggregate(Sum('horas'))['horas__sum'] or 0
#     horas_por_tipo['HC'] -= horas_solicitudes_hc
#     return horas_por_tipo

def calcular_horas_individuales(usuario):
    tipos = ['HE', 'HC']
    horas_por_tipo = {'HE': 0, 'HC': 0}

    for tipo in tipos:
        total_horas = RegistroHoras.objects.filter(
            usuario=usuario,
            tipo=tipo,
            estado='A',
            estado_pago='NP'
        ).aggregate(Sum('horas'))['horas__sum'] or 0
        horas_por_tipo[tipo] = total_horas

    horas_hef = RegistroHoras.objects.filter(
        usuario=usuario,
        tipo='HEF',
        estado='A',
        estado_pago='NP'
    ).aggregate(
        total_horas=Sum('horas'),
        horas_compensatorias_feriado=Sum('horas_compensatorias_feriado')
    )

    horas_por_tipo['HE'] += horas_hef['total_horas'] or 0
    horas_por_tipo['HC'] += horas_hef['horas_compensatorias_feriado'] or 0

    horas_solicitudes_hc = Solicitud.objects.filter(
        usuario=usuario,
        tipo='HC',
        estado='A'
    ).aggregate(Sum('horas'))['horas__sum'] or 0

    horas_por_tipo['HC'] -= horas_solicitudes_hc

    # Incluir horas compensatorias generadas por la conversión
    horas_conversion = ConversionVacacionesHoras.objects.filter(usuario=usuario).aggregate(Sum('horas_compensatorias'))['horas_compensatorias__sum'] or 0
    horas_por_tipo['HC'] += horas_conversion

    return horas_por_tipo



@login_required
def dashboard(request):
    usuario = request.user
    fecha_actual = (now() - timedelta(hours=6)).date()
    fecha_hora_actual = (now() - timedelta(hours=6))

    # Obtener todos los feriados
    feriados = FeriadoNacional.objects.all()
    feriados_fechas = {feriado.fecha for feriado in feriados} 

    dias_data = calcular_dias_disponibles(usuario)
    dias_disponibles = dias_data['dias_disponibles']
    horas_data = calcular_horas_individuales(usuario)
    horas_extra = horas_data['HE']
    horas_compensatorias = horas_data['HC']

    def es_fecha_valida(fecha):
        return fecha.weekday() < 5 and fecha not in feriados_fechas

    def generar_eventos_validos(nombre, tipo, fecha_inicio, fecha_fin, descripcion, color):
        eventos_validos = []
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            if es_fecha_valida(fecha_actual):
                eventos_validos.append({
                    "title": f"{nombre} ({tipo})",
                    "start": fecha_actual.strftime("%Y-%m-%d"),
                    "end": (fecha_actual + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "description": descripcion,
                    "color": color
                })
            fecha_actual += timedelta(days=1)
        return eventos_validos

    eventos = []

    for vacacion in Solicitud.objects.filter(estado='A', tipo='V', fecha_fin__gte=fecha_actual):
        nombre_completo = f"{vacacion.usuario.first_name} {vacacion.usuario.last_name}"
        fecha_inicio = vacacion.fecha_inicio.date()
        fecha_fin = vacacion.fecha_fin.date()
        descripcion = f"Inicio: {fecha_inicio} - Fin: {fecha_fin}"
        eventos += generar_eventos_validos(nombre_completo, "Vacaciones", fecha_inicio, fecha_fin, descripcion, "#e74c3c")

    for hora in Solicitud.objects.filter(estado='A', tipo='HC', fecha_fin__gte=fecha_hora_actual):
        nombre_completo = f"{hora.usuario.first_name} {hora.usuario.last_name}"
        fecha_inicio = hora.fecha_inicio.date()
        fecha_fin = hora.fecha_fin.date()
        descripcion = f"Inicio: {hora.fecha_inicio.strftime('%H:%M')} - Fin: {hora.fecha_fin.strftime('%H:%M')}"
        eventos += generar_eventos_validos(nombre_completo, "Horas Comp", fecha_inicio, fecha_fin, descripcion, "#f39c12")

    for incapacidad in Incapacidad.objects.filter(fecha_fin__gte=fecha_actual):
        nombre_completo = f"{incapacidad.usuario.first_name} {incapacidad.usuario.last_name}"
        fecha_inicio = incapacidad.fecha_inicio.date()
        fecha_fin = incapacidad.fecha_fin.date()
        descripcion = f"Inicio: {fecha_inicio} - Fin: {fecha_fin}"
        eventos += generar_eventos_validos(nombre_completo, "Incapacidad", fecha_inicio, fecha_fin, descripcion, "#9b9b9b")

    for feriado in feriados:
        eventos.append({
            "title": feriado.descripcion,  # Usar el campo descripción del feriado como título
            "start": feriado.fecha.strftime("%Y-%m-%d"),
            "end": (feriado.fecha + timedelta(days=1)).strftime("%Y-%m-%d"),
            "description": f"Feriado: {feriado.descripcion}",
            "color": "#09C1E6"
        })
    

    for licencia in Licencia.objects.filter(estado='A', fecha_fin__gte=fecha_hora_actual):
        nombre_completo = f"{licencia.usuario.first_name} {licencia.usuario.last_name}"
        fecha_inicio = licencia.fecha_inicio.date()
        fecha_fin = licencia.fecha_fin.date()

        if licencia.tipo == 'LAC':
            color = "#1abc9c"
            tipo_evento = "Lactancia"
            descripcion = f"Inicio: {licencia.fecha_inicio.strftime('%H:%M')} - Fin: {(licencia.fecha_inicio + timedelta(hours=1)).strftime('%H:%M')}"

            eventos += generar_eventos_validos(
                nombre_completo,
                tipo_evento,
                fecha_inicio,
                fecha_fin,
                descripcion,
                color,
            )

        elif licencia.tipo == 'MAT':
            color = "#3498db"
            tipo_evento = "Matrimonio"
            descripcion = f"Inicio: {licencia.fecha_inicio.strftime('%d-%m-%Y')} - Fin: {licencia.fecha_fin.strftime('%d-%m-%Y')}"

            eventos += generar_eventos_validos(
                nombre_completo,
                tipo_evento,
                fecha_inicio,
                fecha_fin,
                descripcion,
                color
            )

        elif licencia.tipo == 'CAL':
            color = "#e67e22"
            tipo_evento = "Calamidad Doméstica"
            descripcion = f"Inicio: {licencia.fecha_inicio.strftime('%H:%M')} - Fin: {licencia.fecha_fin.strftime('%H:%M')}"

            eventos += generar_eventos_validos(
                nombre_completo,
                tipo_evento,
                fecha_inicio,
                fecha_fin,
                descripcion,
                color,
            )

    context = {
        'user': usuario,
        'dias_vacaciones_disponibles': dias_disponibles,
        'horas_extra':horas_extra,
        'horas_compensatorias':horas_compensatorias,
        'eventos': json.dumps(eventos),
    }
    return render(request, 'dashboard.html', context)




def PerfilUsuario(request):
    usuario = request.user
    dias_data = calcular_dias_disponibles(usuario)
    dias_disponibles = dias_data['dias_disponibles']

    horas_data = calcular_horas_individuales(usuario)
    horas_compensatorias = horas_data['HC']
    horas_extra = horas_data['HE']
    
    context = {
    'user': usuario,
    'dias_vacaciones_disponibles': dias_disponibles,
    'horas_compensatorias': horas_compensatorias,
    'horas_extra': horas_extra

    }
    return render(request, 'mi_perfil.html', context)

class CambiarContrasenaView(LoginRequiredMixin,PasswordChangeView):
    template_name = 'cambiar_contrasena.html' 
    success_url = reverse_lazy('perfil_usuario')

    def form_valid(self, form):
        messages.success(self.request, '¡Tu contraseña ha sido cambiada exitosamente!')
        return super().form_valid(form)


class CrearUsuarioView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreationForm
    template_name = 'crear_usuario.html'
    success_url = reverse_lazy('dashboard')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.rol in ['GG', 'JI', 'JD']


# def obtener_dias_feriados(request):
#     fecha_inicio = request.GET.get('fecha_inicio', '').split()[0]
#     fecha_fin = request.GET.get('fecha_fin', '').split()[0]

#     try:
#         fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
#         fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()

#         feriados = FeriadoNacional.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
#         feriados_list = [feriado.fecha.strftime("%Y-%m-%d") for feriado in feriados]

#         return JsonResponse({'feriados': feriados_list})
#     except (ValueError, TypeError):
#         return JsonResponse({'error': 'Fechas inválidas'}, status=400)

def obtener_dias_feriados(request):
    try:
        # Obtener parámetros
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return JsonResponse({
                'success': False,
                'message': 'Por favor ingrese las fechas de inicio y fin',
                'feriados': []
            })

        # Convertir fechas
        fecha_inicio = datetime.strptime(fecha_inicio.split()[0], "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(fecha_fin.split()[0], "%Y-%m-%d").date()

        # Validar orden de fechas
        if fecha_inicio > fecha_fin:
            return JsonResponse({
                'success': False,
                'message': 'La fecha de inicio debe ser anterior a la fecha fin',
                'feriados': []
            })

        # Obtener feriados
        feriados = FeriadoNacional.objects.filter(fecha__range=[fecha_inicio, fecha_fin])
        feriados_list = [feriado.fecha.strftime("%Y-%m-%d") for feriado in feriados]

        return JsonResponse({
            'success': True,
            'message': 'Feriados obtenidos correctamente',
            'feriados': feriados_list
        })

    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'message': 'No se pudieron obtener los feriados. Verifique el formato de las fechas (YYYY-MM-DD)',
            'feriados': []
        })
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'No se pudieron obtener los feriados. Por favor intente nuevamente',
            'feriados': []
        })
    
class CrearSolicitudView(LoginRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = 'crear_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        numero_solicitud = uuid.uuid4()
        initial['numero_solicitud'] = f"S-{str(numero_solicitud)[:8]}"  # Tomar los primeros 8 caracteres del UUID
        return initial

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P'
        tipo_solicitud = form.cleaned_data.get('tipo')
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user
        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']
        horas_data = calcular_horas_individuales(usuario)
        horas_compensatorias = horas_data['HC']
        form.instance.requisitos_confirmados = form.cleaned_data.get('confirmacion_requisitos')

        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
        )

        for solicitud in solicitudes_en_conflicto:
            if (solicitud.fecha_inicio <= fecha_inicio <= solicitud.fecha_fin) or \
               (solicitud.fecha_inicio <= fecha_fin <= solicitud.fecha_fin) or \
               (fecha_inicio<= solicitud.fecha_inicio and fecha_fin >= solicitud.fecha_fin):
                print(f"Conflicto con registro: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
                form.add_error(None, "Ya tienes una solicitud registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        incapacidades_conflicto = Incapacidad.objects.filter(
            usuario=usuario
        )

        for incapacidad in incapacidades_conflicto:
            if (incapacidad.fecha_inicio <= fecha_inicio.date() <= incapacidad.fecha_fin) or \
               (incapacidad.fecha_inicio <= fecha_fin.date() <= incapacidad.fecha_fin) or \
               (fecha_inicio.date() <= incapacidad.fecha_inicio and fecha_fin.date() >= incapacidad.fecha_fin):
                print(f"Conflicto con registro: ID {incapacidad.id}, Inicio {incapacidad.fecha_inicio}, Fin {incapacidad.fecha_fin}")
                form.add_error(None, "Ya tienes una incapacidad registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)

        if tipo_solicitud == 'V':
            form.instance.descripcion="Vacaciones"
            total_days_no_work=0
            feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )
            non_working_dates = [
            date for date in (fecha_inicio.date() + timedelta(n) for n in range((fecha_fin.date() - fecha_inicio.date()).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
            ]

            if non_working_dates:
                total_days_no_work = len(non_working_dates)

            fecha_inicio=fecha_inicio.date()
            fecha_fin=fecha_fin.date()
            dias_solicitados = (fecha_fin - fecha_inicio).days +1
            
            fecha_actual = date.today()
            if fecha_inicio<fecha_actual:
                form.add_error(None, "Imposible solicitar vacaciones para fechas menores a la actual.")
                return self.form_invalid(form)

            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados - total_days_no_work} días, pero solo tienes {dias_disponibles} días disponibles."
                )

            form.instance.dias_solicitados = dias_solicitados - total_days_no_work

        elif tipo_solicitud == 'HC':
            form.instance.descripcion="Horas Compensatorias"
            feriados = FeriadoNacional.objects.filter(
                fecha__range=[fecha_inicio.date(), fecha_fin.date()]
            )
            horas_totales = 0
            fecha_actual = fecha_inicio.date()
            tz = get_current_timezone()

            
            print("aaaaa ",fecha_inicio, fecha_fin, fecha_actual)
            while fecha_actual <= fecha_fin.date():
                
                if (fecha_actual.weekday() < 5 and 
                    fecha_actual not in [feriado.fecha for feriado in feriados]):
                    
                    inicioDia = make_aware(datetime.combine(fecha_actual, time(7, 0)), tz)
                    finDia = make_aware(datetime.combine(fecha_actual, time(17, 0)), tz)
                    
                    inicioValido = max(fecha_inicio, inicioDia)
                    finValido = min(fecha_fin, finDia)
                    
                    if inicioValido < finValido:
                        horasDia = (finValido - inicioValido).total_seconds() / 3600
                        
                        almuerzoInicio = make_aware(datetime.combine(fecha_actual, time(12, 0)), tz)
                        almuerzoFin = make_aware(datetime.combine(fecha_actual, time(13, 0)), tz)
                        
                        if inicioValido <= almuerzoInicio < finValido or inicioValido <almuerzoFin <= finValido:
                            horasDia -= 1

                        
                        horasDia = min(horasDia, 9)
                        horas_totales += horasDia
                
                fecha_actual += timedelta(days=1)
            
            horas_solicitadas = horas_totales
            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes Horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)
            
            form.instance.horas = horas_solicitadas

        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        messages.success(self.request, 'Solicitud creada correctamente y pendiente de aprobación.')

        jefe = self.request.user.jefe
        if jefe and jefe.email:
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "numero_solicitud": form.instance.numero_solicitud,
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }

            html_content = render_to_string("mail_solicitud.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Nueva solicitud pendiente de aprobación"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")
        
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']
        horas_data = calcular_horas_individuales(usuario)
        horas_extra = horas_data['HE']
        horas_compensatorias = horas_data['HC']

        context.update({
            'usuario': usuario,
            'dias_vacaciones': dias_disponibles,
            'horas_extra':horas_extra,
            'horas_compensatorias':horas_compensatorias
        })
        return context
    

class AprobarRechazarSolicitudView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Solicitud
    fields = ['estado']
    template_name = 'aprobar_rechazar_solicitud.html'
    success_url = reverse_lazy('lista_solicitudes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        registro = self.get_object()
        usuario = registro.usuario

        dias_data = calcular_dias_disponibles(usuario)
        horas_data = calcular_horas_individuales(usuario)

        context['dias_disponibles'] = dias_data.get('dias_disponibles', 0)
        context['horas_compensatorias'] = horas_data.get('HC', 0)
        context['horas_extras'] = horas_data.get('HE', 0)

        return context

    def test_func(self):
        solicitud = self.get_object()

        if (self.request.user.rol != 'GG' and solicitud.usuario == self.request.user):
            messages.error(self.request, 'No puedes aprobar o rechazar tu propia solicitud.')
            return False


        if self.request.user.is_superuser or self.request.user.rol == 'GG':
            return True
        elif self.request.user.rol == 'JI':
            return solicitud.usuario.departamento.nombre in ['IT', 'ENERGIA', 'INDUSTRIA', 'TALLER','TGU']
        elif self.request.user.rol == 'JD':
            return solicitud.usuario in self.request.user.subordinados.all()
        return False

    def form_valid(self, form):
        solicitud = self.get_object()
        dias_data = calcular_dias_disponibles(solicitud.usuario)
        usuario = solicitud.usuario
        dias_disponibles = dias_data['dias_disponibles']
        fecha_ajustada = now() - timedelta(hours=6)
        año_actual = fecha_ajustada.year
        horas_data = calcular_horas_individuales(solicitud.usuario)
        horas_compensatorias = horas_data['HC']
        
        if form.instance.estado == 'A':
            if solicitud.tipo == 'V':

                if solicitud.dias_solicitados > dias_disponibles:
                    dias_faltantes = solicitud.dias_solicitados - dias_disponibles
                    messages.warning(
                        self.request, 
                        f"Advertencia: Al aprobar esta solicitud, el saldo de días de vacaciones será negativo en {dias_faltantes} días."
                    )
                dias_solicitados = solicitud.dias_solicitados
                historial_vacaciones = HistorialVacaciones.objects.filter(usuario=solicitud.usuario, año=año_actual)
                
                for registro in historial_vacaciones:
                    registro.dias_tomados += dias_solicitados
                    registro.save()

            elif solicitud.tipo == 'HC':
                
                if horas_compensatorias >= solicitud.horas:
                    solicitud.usuario.save()  
                else:
                    messages.error(self.request, "No se puede aprobar. El usuario no tiene suficientes horas compensatorias.")
                    return self.form_invalid(form)

        form.instance.aprobado_por = self.request.user
        messages.success(self.request, 'La solicitud ha sido procesada exitosamente.')
        fecha_ajustada = now() - timedelta(hours=6)
        year = fecha_ajustada.year
        estados = {
        'A': "Aprobada",
        'R': "Rechazada",
        'P': "Pendiente",
    }
        context = {
            "usuario": usuario.first_name,
            "numero_solicitud": solicitud.numero_solicitud,
            "tipo": solicitud.get_tipo_display(),
            "fecha_inicio": solicitud.fecha_inicio.date(),
            "fecha_fin": solicitud.fecha_fin.date(),
            "estado": estados.get(form.instance.estado, "Desconocido"),
            "aprobado_por": form.instance.aprobado_por.get_full_name(),
            "year": year,
            "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
            "enlace_revisar": settings.ENLACE_DEV
        }

        html_content = render_to_string("mail_estado_solicitud.html", context)
        email_sender = MicrosoftGraphEmail()
        subject = f"Tu solicitud ha sido {context['estado']}"

        try:
            email_sender.send_email(
                subject=subject,
                content=html_content,
                to_recipients=[usuario.email],
            )
        except Exception as e:
            print(f"Error al enviar correo al usuario {usuario.email}: {e}")
        return super().form_valid(form)

class EditarMiSolicitudView(LoginRequiredMixin, UpdateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = 'editar_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        if self.object.horas:
            initial['horas'] = self.object.horas
        return initial
    
    def test_func(self):
        solicitud = self.get_object()
        return solicitud.usuario == self.request.user and solicitud.estado == 'P'

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        tipo_solicitud = self.object.tipo
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user
        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']
        horas_data = calcular_horas_individuales(usuario)
        horas_compensatorias = horas_data['HC']
        form.instance.requisitos_confirmados = form.cleaned_data.get('confirmacion_requisitos')


        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
        ).exclude(id=self.object.id)

        for solicitud in solicitudes_en_conflicto:
            if (solicitud.fecha_inicio <= fecha_inicio <= solicitud.fecha_fin) or \
               (solicitud.fecha_inicio <= fecha_fin <= solicitud.fecha_fin) or \
               (fecha_inicio<= solicitud.fecha_inicio and fecha_fin >= solicitud.fecha_fin):
                print(f"Conflicto con registro: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
                form.add_error(None, "Ya tienes una solicitud registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        incapacidades_conflicto = Incapacidad.objects.filter(
            usuario=usuario
        )

        for incapacidad in incapacidades_conflicto:
            if (incapacidad.fecha_inicio <= fecha_inicio.date() <= incapacidad.fecha_fin) or \
               (incapacidad.fecha_inicio <= fecha_fin.date() <= incapacidad.fecha_fin) or \
               (fecha_inicio.date() <= incapacidad.fecha_inicio and fecha_fin.date() >= incapacidad.fecha_fin):
                print(f"Conflicto con registro: ID {incapacidad.id}, Inicio {incapacidad.fecha_inicio}, Fin {incapacidad.fecha_fin}")
                form.add_error(None, "Ya tienes una incapacidad registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)

        if tipo_solicitud == 'V':
            form.instance.descripcion="Vacaciones"
            total_days_no_work=0
            feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )
            non_working_dates = [
            date for date in (fecha_inicio.date() + timedelta(n) for n in range((fecha_fin.date() - fecha_inicio.date()).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
            ]

            if non_working_dates:
                total_days_no_work = len(non_working_dates)

            fecha_inicio=fecha_inicio.date()
            fecha_fin=fecha_fin.date()
            dias_solicitados = (fecha_fin - fecha_inicio).days +1
            
            fecha_actual = date.today()
            if fecha_inicio<fecha_actual:
                form.add_error(None, "Imposible solicitar vacaciones para fechas menores a la actual.")
                return self.form_invalid(form)

            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados - total_days_no_work} días, pero solo tienes {dias_disponibles} días disponibles."
                )

            form.instance.dias_solicitados = dias_solicitados - total_days_no_work

        elif tipo_solicitud == 'HC':
            form.instance.descripcion="Horas Compensatorias"
            feriados = FeriadoNacional.objects.filter(
                fecha__range=[fecha_inicio.date(), fecha_fin.date()]
            )
            horas_totales = 0
            fecha_actual = fecha_inicio.date()
            tz = get_current_timezone()

            while fecha_actual <= fecha_fin.date():
                if (fecha_actual.weekday() < 5 and 
                    fecha_actual not in [feriado.fecha for feriado in feriados]):
                    
                    inicioDia = make_aware(datetime.combine(fecha_actual, time(7, 0)), tz)
                    finDia = make_aware(datetime.combine(fecha_actual, time(17, 0)), tz)
                    
                    inicioValido = max(fecha_inicio, inicioDia)
                    finValido = min(fecha_fin, finDia)
                    
                    if inicioValido < finValido:
                        horasDia = (finValido - inicioValido).total_seconds() / 3600
                        
                        almuerzoInicio = make_aware(datetime.combine(fecha_actual, time(12, 0)), tz)
                        almuerzoFin = make_aware(datetime.combine(fecha_actual, time(13, 0)), tz)
                        
                        if inicioValido <= almuerzoInicio < finValido or inicioValido <almuerzoFin <= finValido:
                            horasDia -= 1
                        
                        horasDia = min(horasDia, 9)
                        horas_totales += horasDia
                
                fecha_actual += timedelta(days=1)
            
            horas_solicitadas = horas_totales
            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes Horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)
            
            form.instance.horas = horas_solicitadas

        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        messages.success(self.request, 'Solicitud creada correctamente y pendiente de aprobación.')

        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "numero_solicitud": form.instance.numero_solicitud,
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "descripcion" : form.instance.descripcion,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }

            html_content = render_to_string("mail_editar_solicitud.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Edición de solicitud pendiente de aprobación"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")


        return super().form_valid(form)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']

        horas_data = calcular_horas_individuales(usuario)
        horas_extra = horas_data['HE']
        horas_compensatorias = horas_data['HC']

        context.update({
            'usuario': usuario,
            'dias_vacaciones': dias_disponibles,
            'horas_extra': horas_extra,
            'horas_compensatorias': horas_compensatorias,
        })
        return context


class EliminarMiSolicitudView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Solicitud
    template_name = 'confirmar_eliminar_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        if self.object.horas:
            initial['horas'] = self.object.horas
        return initial

    def test_func(self):
        solicitud = self.get_object()
        return solicitud.usuario == self.request.user and solicitud.estado == 'P'

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Solicitud eliminada correctamente.")
        return super().delete(request, *args, **kwargs)


class RegistrarHorasView(LoginRequiredMixin, CreateView):
    model = RegistroHoras
    form_class = RegistrarHorasForm
    template_name = 'registrar_horas.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        initial['numero_registro'] = f"RGH-{uuid.uuid4().hex[:8].upper()}"
        return initial


    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P'
        rol_usuario = self.request.user.rol
        tipo_horas = form.cleaned_data.get('tipo')
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user

        anio_actual = date.today().year
        feriados = FeriadoNacional.objects.filter(fecha__year=anio_actual)

        registros_en_conflicto = RegistroHoras.objects.filter(
            usuario=usuario,
        )

        for registro in registros_en_conflicto:
            if (registro.fecha_inicio <= fecha_inicio <= registro.fecha_fin) or \
               (registro.fecha_inicio <= fecha_fin <= registro.fecha_fin) or \
               (fecha_inicio<= registro.fecha_inicio and fecha_fin >= registro.fecha_fin):
                print(f"Conflicto con registro: ID {registro.id}, Inicio {registro.fecha_inicio}, Fin {registro.fecha_fin}")
                form.add_error(None, "Ya tienes un registro que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        if tipo_horas == 'HEF':
            if not feriados.filter(fecha=fecha_inicio.date()).exists():
                form.add_error(None, "El día de inicio no coincide con ningún feriado registrado para este año.")
                return self.form_invalid(form)    

        if rol_usuario == 'TE' and tipo_horas == 'HEF':
            form.add_error(None, "Los Técnicos no pueden registrar horas extras para dias feriados.")
            return self.form_invalid(form)

        elif rol_usuario in ['GG', 'JI', 'JD','IN','AST', 'FNZ'] and tipo_horas == 'HE':
            form.add_error(None, "Usted no puede registrar horas extras.")
            return self.form_invalid(form)
        
        form.instance.numero_registro = form.cleaned_data['numero_registro']


        messages.success(self.request, 'Registro de horas creado y pendiente de aprobación.')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "numero_solicitud": form.instance.numero_registro,
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": form.instance.fecha_inicio,
                "fecha_fin": form.instance.fecha_fin,
                "descripcion":form.instance.descripcion,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar": settings.ENLACE_DEV, 
            }

            html_content = render_to_string("mail_solicitud.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Nuevo registro de horas pendiente de aprobación"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        horas_data = calcular_horas_individuales(usuario)
        horas_extra = horas_data['HE']
        horas_compensatorias = horas_data['HC']

        context.update({
            'usuario': usuario,
            'horas_extra':horas_extra,
            'horas_compensatorias':horas_compensatorias
        })
        return context

class AprobarRechazarHorasView(UserPassesTestMixin, UpdateView):
    model = RegistroHoras
    fields = ['estado']
    template_name = 'aprobar_rechazar_horas.html'
    success_url = reverse_lazy('lista_solicitudes')
    
    
    def test_func(self):
        registro = self.get_object()
        return registro.usuario != self.request.user and self.request.user.rol in ['GG', 'JI', 'JD']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        registro = self.get_object()
        usuario = registro.usuario

        dias_data = calcular_dias_disponibles(usuario)
        horas_data = calcular_horas_individuales(usuario)

        context['dias_disponibles'] = dias_data.get('dias_disponibles', 0)
        context['horas_compensatorias'] = horas_data.get('HC', 0)
        context['horas_extras'] = horas_data.get('HE', 0)
        
        return context
    
    def form_valid(self, form):
        registro = self.get_object()
        usuario = registro.usuario
        if form.instance.estado == 'A':  
            if registro.tipo =='HEF':
                registro.save()
            form.instance.aprobado_por = self.request.user
            messages.success(self.request, 'El registro de horas ha sido procesado Aprobado exitosamente.')
        
        elif form.instance.estado == 'R':
            messages.warning(
                self.request,
                f"El registro de horas con el número {registro.numero_registro} ha sido rechazado."
            )

        elif form.instance.estado == 'P':
            messages.warning(
                self.request,
                f"El registro de horas con el número {registro.numero_registro} ha sido marcado como pendiente."
            )

        fecha_ajustada = now() - timedelta(hours=6)
        year = fecha_ajustada.year
        estados = {
            'A': "Aprobada",
            'R': "Rechazada",
            'P': "Pendiente",
        }
        context = {
            "usuario": usuario.first_name,
            "numero_solicitud": registro.numero_registro,
            "tipo": registro.get_tipo_display(),
            "fecha_inicio": registro.fecha_inicio,
            "fecha_fin": registro.fecha_fin,
            "estado": estados.get(form.instance.estado, "Desconocido"), 
            "aprobado_por": form.instance.aprobado_por.get_full_name(),
            "year": year,
            "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
            "enlace_revisar": settings.ENLACE_DEV
        }

        html_content = render_to_string("mail_estado_solicitud.html", context)
        email_sender = MicrosoftGraphEmail()
        subject = f"Tu solicitud ha sido {context['estado']}"

        try:
            email_sender.send_email(
                subject=subject,
                content=html_content,
                to_recipients=[usuario.email],
            )
        except Exception as e:
            print(f"Error al enviar correo al usuario {usuario.email}: {e}")
        return super().form_valid(form)


class EditarMiRegistroHorasView(LoginRequiredMixin, UpdateView):
    model = RegistroHoras
    form_class = RegistrarHorasForm
    template_name = 'editar_registro_horas.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        horas_data = calcular_horas_individuales(usuario)
        context.update({
            'horas_extra': horas_data['HE'],
            'horas_compensatorias': horas_data['HC'],
        })
        return context

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P'
        rol_usuario = self.request.user.rol
        tipo_horas = form.cleaned_data.get('tipo')
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user
        registro = self.get_object()

        anio_actual = date.today().year
        feriados = FeriadoNacional.objects.filter(fecha__year=anio_actual)

        registros_en_conflicto = RegistroHoras.objects.filter(
            usuario=usuario,
        ).exclude(pk=self.object.pk)

        for registro in registros_en_conflicto:
            if (registro.fecha_inicio <= fecha_inicio <= registro.fecha_fin) or \
               (registro.fecha_inicio <= fecha_fin <= registro.fecha_fin) or \
               (fecha_inicio<= registro.fecha_inicio and fecha_fin >= registro.fecha_fin):
                print(f"Conflicto con registro: ID {registro.id}, Inicio {registro.fecha_inicio}, Fin {registro.fecha_fin}")
                form.add_error(None, "Ya tienes un registro que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        if tipo_horas == 'HEF':
            if not feriados.filter(fecha=fecha_inicio.date()).exists():
                form.add_error(None, "El día de inicio no coincide con ningún feriado registrado para este año.")
                return self.form_invalid(form)    

        if rol_usuario == 'TE' and tipo_horas == 'HEF':
            form.add_error(None, "Los Técnicos no pueden registrar horas extras para dias feriados.")
            return self.form_invalid(form)

        elif rol_usuario in ['GG', 'JI', 'JD','IN','AST', 'FNZ'] and tipo_horas == 'HE':
            form.add_error(None, "Usted no puede registrar horas extras.")
            return self.form_invalid(form)
        
        form.instance.numero_registro = form.cleaned_data['numero_registro']

        messages.success(self.request, f"El registro de horas {registro.numero_registro} ha sido actualizado.")
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "numero_solicitud": form.instance.numero_registro,
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": form.instance.fecha_inicio,
                "fecha_fin": form.instance.fecha_fin,
                "descripcion":form.instance.descripcion,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar": settings.ENLACE_DEV, 
            }

            html_content = render_to_string("mail_editar_solicitud.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Edición de registro de horas pendiente de aprobación"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")

        
        return super().form_valid(form)

class EliminarMiRegistroHorasView(LoginRequiredMixin, DeleteView):
    model = RegistroHoras
    template_name = 'confirmar_eliminar_registro.html'
    success_url = reverse_lazy('mis_solicitudes')

    def delete(self, request, *args, **kwargs):
        registro = self.get_object()
        messages.success(request, f"El registro de horas {registro.numero_registro} ha sido eliminado exitosamente.")
        return super().delete(request, *args, **kwargs)


class ListaSolicitudesRegistrosPendientesView(ListView):
    template_name = 'lista_solicitudes.html'
    context_object_name = 'pendientes'
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol not in ['GG', 'JI', 'JD']:
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        registros_queryset = RegistroHoras.objects.filter(estado='P')
        solicitudes_queryset = Solicitud.objects.filter(estado='P')
        licencias_queryset = Licencia.objects.filter(estado='P')

        print(licencias_queryset)

        if user.rol in ['GG', 'JI', 'JD']:
            registros_queryset = registros_queryset.filter(usuario__in=user.subordinados.all())
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=user.subordinados.all())
            licencias_queryset = licencias_queryset.filter(usuario__in=user.subordinados.all())
        else:
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()
            licencias_queryset = Licencia.objects.none()

        pendientes = list(solicitudes_queryset) + list(registros_queryset) + list(licencias_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3} 
        for item in pendientes:
            if isinstance(item, Solicitud):
                item.tipo_objeto = 'solicitud'
            elif isinstance(item, RegistroHoras):
                item.tipo_objeto = 'registro'
            elif isinstance(item, Licencia):
                item.tipo_objeto = 'licencia'
            else:
                item.tipo_objeto = 'desconocido'
                
            item.estado_orden = estado_prioridad.get(item.estado, 4)


        pendientes = sorted(pendientes, key=attrgetter('estado_orden', 'fecha_inicio'))
        paginator = Paginator(pendientes,8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['pendientes'] = page_obj
        context['page_obj'] = page_obj

        return context

class ListaSolicitudesRegistrosDosNivelesView(ListView):
    template_name = 'lista_solicitudes_dos_niveles.html'
    context_object_name = 'pendientes'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol not in ['GG', 'JI', 'JD']:
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)

    def obtener_subordinados_dos_niveles(self, usuario):
        subordinados_nivel_1 = Usuario.objects.filter(jefe=usuario)
        subordinados_nivel_2 = Usuario.objects.filter(jefe__in=subordinados_nivel_1)
        return subordinados_nivel_2

    def get_queryset(self):
        user = self.request.user
        registros_queryset = RegistroHoras.objects.filter(estado='P')
        solicitudes_queryset = Solicitud.objects.filter(estado='P')
        licencias_queryset = Licencia.objects.filter(estado='P')

        if user.rol in ['GG', 'JI', 'JD']:
            subordinados = self.obtener_subordinados_dos_niveles(user)
            registros_queryset = registros_queryset.filter(usuario__in=subordinados)
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=subordinados)
            licencias_queryset = licencias_queryset.filter(usuario__in=subordinados)
        else:
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()
            licencias_queryset = Licencia.objects.none()

        pendientes = list(solicitudes_queryset) + list(registros_queryset) + list(licencias_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}
        for item in pendientes:
            if isinstance(item, Solicitud):
                item.tipo_objeto = 'solicitud'
            elif isinstance(item, RegistroHoras):
                item.tipo_objeto = 'registro'
            elif isinstance(item, Licencia):
                item.tipo_objeto = 'licencia'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        return sorted(pendientes, key=attrgetter('estado_orden', 'fecha_inicio'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = Paginator(self.get_queryset(), 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['pendientes'] = page_obj
        context['page_obj'] = page_obj
        return context


class HistorialCombinadoView(LoginRequiredMixin, ListView):
    template_name = 'historial_solicitudes.html'
    context_object_name = 'registros_y_solicitudes'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol not in ['GG', 'JI', 'JD']:
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        estado = self.request.GET.get('estado')
        tipo = self.request.GET.get('tipo')
        usuario_id = self.request.GET.get('usuario')
        
        registros_queryset = RegistroHoras.objects.filter(usuario__in=user.subordinados.all())
        solicitudes_queryset = Solicitud.objects.filter(usuario__in=user.subordinados.all())
        licencias_queryset = Licencia.objects.filter(usuario__in=user.subordinados.all())

        if estado:
            registros_queryset = registros_queryset.filter(estado=estado)
            solicitudes_queryset = solicitudes_queryset.filter(estado=estado)
            licencias_queryset = licencias_queryset.filter(estado=estado)
        if tipo:
            solicitudes_queryset = solicitudes_queryset.filter(tipo=tipo)
            licencias_queryset = licencias_queryset.filter(tipo=tipo)
        if usuario_id:
            registros_queryset = registros_queryset.filter(usuario_id=usuario_id)
            solicitudes_queryset = solicitudes_queryset.filter(usuario_id=usuario_id)
            licencias_queryset = licencias_queryset.filter(usuario_id=usuario_id)

        registros_y_solicitudes = list(registros_queryset) + list(solicitudes_queryset) + list(licencias_queryset)
        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}

        print(registros_y_solicitudes)
        
        for item in registros_y_solicitudes:
            if isinstance(item, Solicitud):
                item.tipo_objeto = 'solicitud'
            elif isinstance(item, RegistroHoras):
                item.tipo_objeto = 'registro'
            elif isinstance(item, Licencia):
                item.tipo_objeto = 'licencia'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        return sorted(registros_y_solicitudes, key=attrgetter('estado_orden', 'fecha_inicio'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        paginator = Paginator(self.get_queryset(), 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        context['subordinados'] = user.subordinados.all()
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)
        return context

@login_required
def reporte_solicitudes(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")
    
    solicitudes = Solicitud.objects.filter(
        estado_cierre=0,
        estado='A'
    ).order_by('usuario', 'fecha_inicio')

    solicitudes_por_usuario = {}
    for solicitud in solicitudes:
        usuario = solicitud.usuario
        if usuario not in solicitudes_por_usuario:
            solicitudes_por_usuario[usuario] = {'solicitudes': [], 'total_dias': 0, 'total_horas': 0}
        
        solicitudes_por_usuario[usuario]['solicitudes'].append(solicitud)
        solicitudes_por_usuario[usuario]['total_dias'] += solicitud.dias_solicitados or 0
        solicitudes_por_usuario[usuario]['total_horas'] += solicitud.horas or 0

    hay_solicitudes_pendientes = solicitudes.exists()

    if request.method == "POST":
        seleccionados = request.POST.getlist('seleccionados')
        if 'marcar_cerrado' in request.POST:
            if seleccionados:
                solicitudes_actualizadas = Solicitud.objects.filter(id__in=seleccionados).update(estado_cierre=1)
                messages.success(request, f"{solicitudes_actualizadas} solicitudes han sido marcadas como cerradas.")
                return redirect('reporte_solicitudes')
            else:
                messages.warning(request, "Por favor selecciona al menos una solicitud para marcar como cerrada.")
        
        elif 'generar_reporte' in request.POST:
            request.session['reporte_solicitudes'] = seleccionados
            return redirect('generar_reporte_solicitudes_pdf')

    paginator = Paginator(list(solicitudes_por_usuario.items()), 5) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reporte_solicitudes.html', {
        'page_obj': page_obj,
        'hay_solicitudes_pendientes': hay_solicitudes_pendientes,
        'fecha_reporte': now(),
    })

@login_required
def generar_reporte_solicitudes_pdf(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    solicitudes = Solicitud.objects.filter(estado='A', estado_cierre=False).order_by('usuario', 'fecha_inicio')
    solicitudes_por_usuario = {}
    for solicitud in solicitudes:
        usuario = solicitud.usuario
        if usuario not in solicitudes_por_usuario:
            solicitudes_por_usuario[usuario] = {
                'solicitudes': [],
                'total_dias': 0,
                'total_horas': 0,
            }
        solicitudes_por_usuario[usuario]['solicitudes'].append(solicitud)
        if solicitud.dias_solicitados:
            solicitudes_por_usuario[usuario]['total_dias'] += solicitud.dias_solicitados
        if solicitud.horas:
            solicitudes_por_usuario[usuario]['total_horas'] += solicitud.horas

    context = {
        'solicitudes_por_usuario': solicitudes_por_usuario,
        'fecha_reporte': now(),
    }

    template = get_template('reporte_solicitudes_pdf.html')
    html = template.render(context)
    fecha_actual = datetime.now().strftime("%Y:%m:%d")
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_solicitudes_{fecha_actual}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response, encoding='UTF-8')

    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=400)

    return response

class MiSolicitudYRegistroView(LoginRequiredMixin,ListView):
    template_name = 'mis_solicitudes.html'
    context_object_name = 'solicitudes_y_registros'

    def get_queryset(self):
        return [] 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user


        solicitudes_queryset = Solicitud.objects.filter(usuario=user)
        registros_queryset = RegistroHoras.objects.filter(usuario=user)

        estado = self.request.GET.get('estado')
        if estado:
            solicitudes_queryset = solicitudes_queryset.filter(estado=estado)
            registros_queryset = registros_queryset.filter(estado=estado)

        solicitudes_y_registros = list(solicitudes_queryset) + list(registros_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}
        for item in solicitudes_y_registros:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        solicitudes_y_registros = sorted(solicitudes_y_registros, key=attrgetter('estado_orden', 'fecha_inicio'))

        paginator = Paginator(solicitudes_y_registros,8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['solicitudes_y_registros'] = page_obj
        context['page_obj'] = page_obj
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)
        return context


def ajuste_vacaciones(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    usuarios = Usuario.objects.filter(is_superuser=False)
    usuarios_vacaciones = []
    timezone_utc_minus_6 = pytz.timezone('Etc/GMT+6')
    utc_minus_6 = datetime.now(timezone_utc_minus_6)
    formatted_time = utc_minus_6.strftime('%d/%m/%Y %H:%M')

    for usuario in usuarios:
        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']
        total_dias_asignados=dias_data['total_asignados']
        total_dias_tomados=dias_data['total_tomados']
        total_dias_ajustados=dias_data['total_ajustados']

        usuarios_vacaciones.append({
            'usuario': usuario,
            'dias_asignados': total_dias_asignados,
            'dias_tomados': total_dias_tomados,
            'dias_ajustados': total_dias_ajustados,
            'dias_disponibles': dias_disponibles,
        })

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        usuario = get_object_or_404(Usuario, id=usuario_id)
        form = AjusteVacacionesForm(request.POST)
        
        if form.is_valid():
            ajuste = form.save(commit=False)
            ajuste.usuario = usuario
            ajuste.ajustado_por = request.user
            ajuste.año = date.today().year
            ajuste.save()

            context = {
                'ajustado_por': request.user.get_full_name(),
                'usuario': usuario.get_full_name(),
                'dias_ajustados': ajuste.dias_ajustados,
                'total_dias_disponibles': calcular_dias_disponibles(usuario)['dias_disponibles'],
                'fecha_ajuste':formatted_time,
            
            }
            html_content = render_to_string("mail_ajuste_vacaciones.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = f"Ajuste de Vacaciones"

            try:
                email_sender.send_email(
                    subject=subject,
                    content=html_content,
                    to_recipients=[usuario.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al usuario {usuario.email}: {e}")

            messages.success(request, f"Vacaciones ajustadas para {usuario.get_full_name()}")
            return redirect('ajuste_vacaciones')
    else:
        form = AjusteVacacionesForm()

    context = {
        'usuarios_vacaciones': usuarios_vacaciones,
        'form': form,
    }
    return render(request, 'ajuste_vacaciones.html', context)


@login_required
def historial_ajustes_vacaciones(request):
    if request.user.rol != 'GG':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")
    ajustes = AjusteVacaciones.objects.select_related('usuario', 'ajustado_por').order_by('-fecha_ajuste')
    return render(request, 'historial_ajustes_vacaciones.html', {'ajustes': ajustes})


@login_required
def reporte_horas_extra_html(request):
    # Verificar permisos
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    # Filtrar registros
    registros = RegistroHoras.objects.filter(
        Q(tipo='HE') | Q(tipo='HEF'),
        estado='A',
        estado_pago='NP'
    ).order_by('usuario', 'fecha_inicio')

    registros_por_usuario = {}
    for registro in registros:
        usuario = registro.usuario
        if usuario not in registros_por_usuario:
            registros_por_usuario[usuario] = {'registros': [], 'total_horas': 0}
        
        registros_por_usuario[usuario]['registros'].append(registro)
        registros_por_usuario[usuario]['total_horas'] += registro.horas

    hay_registros_pendientes = registros.exists()

    if request.method == "POST":
        seleccionados = request.POST.getlist('seleccionados')
        if 'marcar_pagado' in request.POST:
            registros_actualizados = RegistroHoras.objects.filter(id__in=seleccionados).update(estado_pago='PG')
            messages.success(request, f"{registros_actualizados} registros de horas extras han sido marcados como pagados.")
            return redirect('reporte_horas_extra')

        elif 'generar_reporte' in request.POST:
            request.session['reporte_horas_extra'] = seleccionados
            return redirect('generar_pdf')

    paginator = Paginator(list(registros_por_usuario.items()), 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reporte_horas_extra.html', {
        'page_obj': page_obj,
        'hay_registros_pendientes': hay_registros_pendientes,
    })



class reporte_horas_extra_PDF(LoginRequiredMixin,View):
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
            except:
                pass

        registros = RegistroHoras.objects.filter(
            Q(tipo='HE') | Q(tipo='HEF'),
            estado='A',
            estado_pago='NP'
        ).order_by('fecha_inicio')

        registros_por_usuario = {}
        for registro in registros:
            usuario_nombre = registro.usuario.get_full_name()
            if usuario_nombre not in registros_por_usuario:
                registros_por_usuario[usuario_nombre] = {
                    'registros': [],
                    'total_horas': 0,
                }
            registros_por_usuario[usuario_nombre]['registros'].append({
                'numero_registro': registro.numero_registro,
                'numero_proyecto': registro.numero_proyecto,
                'fecha_inicio': registro.fecha_inicio,
                'fecha_fin': registro.fecha_fin,
                'horas': f"{registro.horas:.2f}",
                'descripcion': registro.descripcion or ''
            })
            registros_por_usuario[usuario_nombre]['total_horas'] += float(registro.horas)

        context = {
            'registros_por_usuario': registros_por_usuario,
            'year': timezone.now().year,
            'fecha_reporte': now(),
        }

        template = get_template('reporte_horas_extra_pdf.html')
        html = template.render(context)
        fecha_actual = datetime.now().strftime("%Y:%m:%d")
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="reporte_horas_extra_{fecha_actual}.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response, encoding='UTF-8')

        if pisa_status.err:
            return HttpResponse('Error al generar el PDF', status=400)
        return response
    

class CrearIncapacidadView(LoginRequiredMixin, CreateView):
    model = Incapacidad
    form_class = IncapacidadForm
    template_name = 'crear_incapacidad.html'
    success_url = reverse_lazy('mis_incapacidades')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user

        fecha_actual = date.today()
        if fecha_inicio > fecha_actual:
            form.add_error(None, "Imposible registrar una incapacidad para el futuro.")
            return self.form_invalid(form)
        
        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio, fecha_fin]
        )

        non_working_dates = [
            date for date in (fecha_inicio + timedelta(n) for n in range((fecha_fin - fecha_inicio).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
        ]

        if non_working_dates:
            non_working_str = ", ".join(date.strftime("%d/%m/%Y (%A)") for date in non_working_dates)
            form.add_error(None, f"La incapacidad incluye días no laborables: {non_working_str}. Por favor, selecciona otro rango.")
            return self.form_invalid(form)
        
        incapacidades_conflicto = Incapacidad.objects.filter(
            usuario=usuario
        )

        for incapacidad in incapacidades_conflicto:
            if (incapacidad.fecha_inicio <= fecha_inicio <= incapacidad.fecha_fin) or \
               (incapacidad.fecha_inicio <= fecha_fin <= incapacidad.fecha_fin) or \
               (fecha_inicio<= incapacidad.fecha_inicio and fecha_fin >= incapacidad.fecha_fin):
                print(f"Conflicto con registro: ID {incapacidad.id}, Inicio {incapacidad.fecha_inicio}, Fin {incapacidad.fecha_fin}")
                form.add_error(None, "Ya tienes una incapacidad registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
        )

        for solicitud in solicitudes_en_conflicto:
            if (solicitud.fecha_inicio.date() <= fecha_inicio <= solicitud.fecha_fin.date()) or \
               (solicitud.fecha_inicio.date() <= fecha_fin<= solicitud.fecha_fin.date()) or \
               (fecha_inicio<= solicitud.fecha_inicio.date() and fecha_fin>= solicitud.fecha_fin.date()):
                print(f"Conflicto con registro: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
                form.add_error(None, "Ya tienes una solicitud registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
        
        if not form.cleaned_data.get('archivo_adjunto'):
            form.add_error('archivo', "Debes adjuntar un archivo.")
            return self.form_invalid(form)
        
        messages.success(self.request, 'Incapacidad creada correctamente')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }
            html_content = render_to_string("mail_incapacidades.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Registro de Incapacidad"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")
        return super().form_valid(form)


class GenerarReporteIncapacidadesView(LoginRequiredMixin,View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        incapacidades = Incapacidad.objects.filter(revisado=False).order_by('fecha_inicio')

        incapacidades_por_usuario = {}
        for incapacidad in incapacidades:
            usuario_nombre = incapacidad.usuario.get_full_name()
            if usuario_nombre not in incapacidades_por_usuario:
                incapacidades_por_usuario[usuario_nombre] = {
                    'incapacidades': [],
                    'total_dias': 0,
                }
            incapacidades_por_usuario[usuario_nombre]['incapacidades'].append({
                'fecha_inicio': incapacidad.fecha_inicio,
                'fecha_fin': incapacidad.fecha_fin,
                'dias_incapacidad': incapacidad.dias_incapacidad,
                'descripcion': incapacidad.descripcion or '',
            })
            incapacidades_por_usuario[usuario_nombre]['total_dias'] += incapacidad.dias_incapacidad

        context = {
            'incapacidades_por_usuario': incapacidades_por_usuario,
            'fecha_reporte': timezone.now().year,
        }
        template = get_template('reporte_incapacidades_pdf.html')
        html = template.render(context)
        fecha_actual = datetime.now().strftime("%Y:%m:%d")
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="reporte_incapacidades_{fecha_actual}.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response, encoding='UTF-8')

        if pisa_status.err:
            return HttpResponse('Error al generar el PDF', status=400)
        return response


@login_required
def lista_incapacidades(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    incapacidades = Incapacidad.objects.filter(revisado=False).order_by('usuario', '-fecha_inicio')
    incapacidades_por_usuario = {}
    for incapacidad in incapacidades:
        usuario = incapacidad.usuario
        if usuario not in incapacidades_por_usuario:
            incapacidades_por_usuario[usuario] = {'incapacidades': [], 'total_dias': 0}
        incapacidades_por_usuario[usuario]['incapacidades'].append(incapacidad)
        incapacidades_por_usuario[usuario]['total_dias'] += incapacidad.dias_incapacidad

    hay_incapacidades_pendientes = incapacidades.exists()

    if request.method == "POST":
        seleccionados = request.POST.getlist('seleccionados')
        if 'marcar_revisado' in request.POST:
            if seleccionados:
                incapacidades_actualizadas = Incapacidad.objects.filter(id__in=seleccionados).update(revisado=True)
                messages.success(request, f"{incapacidades_actualizadas} incapacidades han sido marcadas como revisadas.")
                return redirect('lista_incapacidades')
            else:
                messages.warning(request, "Por favor selecciona al menos una incapacidad para marcar como revisada.")

        elif 'generar_reporte' in request.POST:
            request.session['reporte_incapacidades'] = seleccionados
            return redirect('generar_reporte_incapacidades')

    # Paginación
    paginator = Paginator(list(incapacidades_por_usuario.items()), 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'lista_incapacidades.html', {
        'page_obj': page_obj,
        'hay_incapacidades_pendientes': hay_incapacidades_pendientes,
    })


class MisIncapacidadesView(LoginRequiredMixin, ListView):
    model = Incapacidad
    template_name = 'mis_incapacidades.html'
    context_object_name = 'mis_incapacidades'

    def get_queryset(self):
        return Incapacidad.objects.filter(usuario=self.request.user).order_by('-fecha_inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        incapacidades = self.get_queryset()
        paginator = Paginator(incapacidades, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['page_obj'] = page_obj
        return context
    
class EditarIncapacidadView(LoginRequiredMixin, UpdateView):
    model = Incapacidad
    form_class = IncapacidadForm
    template_name = 'editar_incapacidad.html'
    success_url = reverse_lazy('mis_incapacidades')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.usuario != self.request.user:
            raise PermissionDenied
        if not obj.es_eliminable():
            raise PermissionDenied("No puedes editar esta incapacidad porque la fecha de inicio ya pasó.")
        return obj

    def form_valid(self, form):
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user
        fecha_actual = date.today()
        if fecha_inicio > fecha_actual:
            form.add_error(None, "Imposible registrar una incapacidad para el futuro.")
            return self.form_invalid(form)

        incapacidades_conflicto = Incapacidad.objects.filter(
            usuario=usuario
        ).exclude(pk=self.object.pk)

        for incapacidad in incapacidades_conflicto:

            if (incapacidad.fecha_inicio <= fecha_inicio <= incapacidad.fecha_fin) or \
               (incapacidad.fecha_inicio <= fecha_fin <= incapacidad.fecha_fin) or \
               (fecha_inicio <= incapacidad.fecha_inicio and fecha_fin >= incapacidad.fecha_fin):
                print(f"Conflicto con registro: ID {incapacidad.id}, Inicio {incapacidad.fecha_inicio}, Fin {incapacidad.fecha_fin}")
                form.add_error(None, "Ya tienes una incapacidad registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
        
        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
        )

        for solicitud in solicitudes_en_conflicto:
            if (solicitud.fecha_inicio.date() <= fecha_inicio <= solicitud.fecha_fin.date()) or \
               (solicitud.fecha_inicio.date() <= fecha_fin <= solicitud.fecha_fin.date()) or \
               (fecha_inicio<= solicitud.fecha_inicio.date() and fecha_fin >= solicitud.fecha_fin.date()):
                print(f"Conflicto con registro: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
                form.add_error(None, "Ya tienes una solicitud registrada que se solapa con este rango. Por favor, selecciona otro rango")
                return self.form_invalid(form)
            
        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio, fecha_fin]
        )

        non_working_dates = [
            date for date in (fecha_inicio + timedelta(n) for n in range((fecha_fin - fecha_inicio).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
        ]

        if non_working_dates:
            non_working_str = ", ".join(date.strftime("%d/%m/%Y (%A)") for date in non_working_dates)
            form.add_error(None, f"La incapacidad incluye días no laborables: {non_working_str}. Por favor, selecciona otro rango.")
            return self.form_invalid(form)

        form.instance.usuario = self.request.user

        messages.success(self.request, 'Incapacidad actualizada correctamente')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }

            html_content = render_to_string("mail_incapacidades.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Registro de Incapacidad"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")

        return super().form_valid(form)

class EliminarIncapacidadView(LoginRequiredMixin, DeleteView):
    model = Incapacidad
    template_name = 'confirmar_eliminar_incapacidad.html'
    success_url = reverse_lazy('mis_incapacidades')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.usuario != self.request.user or not obj.es_eliminable():
            raise PermissionDenied("No puedes eliminar esta incapacidad por que la fecha de la incapacidad ya inició.")
        return obj
    

class FeriadoNacionalListView(LoginRequiredMixin, ListView):
    model = FeriadoNacional
    template_name = 'feriados/feriado_list.html'
    context_object_name = 'feriados'

class FeriadoNacionalCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FeriadoNacional
    form_class = FeriadoNacionalForm
    template_name = 'feriados/feriado_form.html'
    success_url = reverse_lazy('feriado_list')

    def test_func(self):
        return self.request.user.is_superuser 

class FeriadoNacionalUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = FeriadoNacional
    form_class = FeriadoNacionalForm
    template_name = 'feriados/feriado_form.html'
    success_url = reverse_lazy('feriado_list')

    def test_func(self):
        return self.request.user.is_superuser 

class FeriadoNacionalDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FeriadoNacional
    template_name = 'feriados/feriado_confirm_delete.html'
    success_url = reverse_lazy('feriado_list')

    def test_func(self):
        return self.request.user.is_superuser


@login_required
def colaboradores_info(request):
    if request.user.rol != 'GG':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    colaboradores = Usuario.objects.filter(is_superuser=False)
    colaboradores_data = []

    for colaborador in colaboradores:
        dias_data = calcular_dias_disponibles(colaborador)
        horas_data = calcular_horas_individuales(colaborador)

        colaboradores_data.append({
            'usuario': colaborador,
            'dias_data': dias_data,
            'horas_data': horas_data,
        })

    context = {
        'colaboradores_data': colaboradores_data,
    }
    return render(request, 'colaboradores_info.html', context)


def logout_view(request):
    logout(request)
    return redirect('login')


class CrearLicenciaView(CreateView):
    model = Licencia
    form_class = LicenciaForm
    template_name = 'crear_licencia.html'
    success_url = reverse_lazy('mis_licencias')

    def calcular_fecha_lactancia(self, fecha_inicio):
        fecha_final = fecha_inicio + relativedelta(months=6)
        fecha_final = fecha_final.replace(hour=fecha_inicio.hour + 1, minute=0, second=0)
        return fecha_final

    def calcular_fecha_matrimonio(self, fecha_inicio):
        fecha_actual = fecha_inicio.date()
        total_dias = 0

        while total_dias < 3:
            if fecha_actual.weekday() < 5 and not FeriadoNacional.objects.filter(fecha=fecha_actual).exists():
                total_dias += 1
                if total_dias == 3:
                    break
            fecha_actual += timedelta(days=1)

        return datetime.combine(fecha_actual, time(23,59, 59))

    def calcular_horas_calamidad(self, fecha_inicio, fecha_fin):

        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )
        horas_totales = Decimal(0)
        fecha_actual = fecha_inicio.date()
        tz = get_current_timezone()

        while fecha_actual <= fecha_fin.date():
            if (fecha_actual.weekday() < 5 and 
                fecha_actual not in [feriado.fecha for feriado in feriados]):

                inicioDia = make_aware(datetime.combine(fecha_actual, time(7, 0)), tz)
                finDia = make_aware(datetime.combine(fecha_actual, time(17, 0)), tz)

                inicioValido = max(fecha_inicio, inicioDia)
                finValido = min(fecha_fin, finDia)

                if inicioValido < finValido:
                    horasDia = Decimal((finValido - inicioValido).total_seconds() / 3600)

                    almuerzoInicio = make_aware(datetime.combine(fecha_actual, time(12, 0)), tz)
                    almuerzoFin = make_aware(datetime.combine(fecha_actual, time(13, 0)), tz)

                    if inicioValido <= almuerzoInicio < finValido or inicioValido < almuerzoFin <= finValido:
                        horasDia -= Decimal(1)

                    horasDia = min(horasDia, Decimal(9))
                    horas_totales += horasDia

            fecha_actual += timedelta(days=1)

        return horas_totales



    def form_valid(self, form):
        licencia = form.save(commit=False)
        licencia.usuario = self.request.user

        if licencia.tipo == 'LAC':
            almuerzo_inicio = licencia.fecha_inicio.replace(hour=12, minute=0, second=0)
            almuerzo_fin = licencia.fecha_inicio.replace(hour=13, minute=0, second=0)

            if almuerzo_inicio <= licencia.fecha_inicio < almuerzo_fin:
                form.add_error('fecha_inicio', "La hora de inicio no puede ser durante el almuerzo (12:00 - 13:00).")
                return self.form_invalid(form)

            licencia.fecha_fin = self.calcular_fecha_lactancia(licencia.fecha_inicio)
            licencia.horas_totales = 1

        elif licencia.tipo == 'MAT':
            licencia.fecha_inicio = datetime.combine(licencia.fecha_inicio.date(), time(0, 0, 0))
            licencia.fecha_fin = self.calcular_fecha_matrimonio(licencia.fecha_inicio)
            licencia.dias_totales = 3
            licencia.estado = 'P'

        elif licencia.tipo == 'CAL':  # Lógica para Calamidad
            licencia.horas_totales = self.calcular_horas_calamidad(licencia.fecha_inicio, licencia.fecha_fin)
            horas_acumuladas = Licencia.objects.filter(
                usuario=licencia.usuario,
                tipo='CAL',
                fecha_inicio__year=licencia.fecha_inicio.year
            ).exclude(pk=licencia.pk).aggregate(models.Sum('horas_totales'))['horas_totales__sum'] or Decimal(0)

            if Decimal(horas_acumuladas) + licencia.horas_totales > Decimal(135):
                form.add_error('fecha_fin', "No puedes exceder las 135 horas anuales para Calamidad Doméstica.")
                return self.form_invalid(form)

        licencia.save()
        messages.success(self.request, "La licencia se ha registrado correctamente.")
        jefe = self.request.user.jefe
        if jefe and jefe.email:
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": licencia.fecha_inicio,
                "fecha_fin": licencia.fecha_fin,
                "descripcion": form.instance.descripcion,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }

            html_content = render_to_string("mail_licencia.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Nueva licencia agregada"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")
        return super().form_valid(form)



class MisLicenciasView(ListView):
    model = Licencia
    template_name = 'mis_licencias.html'
    context_object_name = 'licencias'
    paginate_by = 10

    def get_queryset(self):
        return Licencia.objects.filter(usuario=self.request.user).order_by('-fecha_inicio')


class AprobarRechazarLicenciaView(UserPassesTestMixin, UpdateView):
    model = Licencia
    fields = ['estado']
    template_name = 'aprobar_rechazar_licencia.html'
    success_url = reverse_lazy('lista_solicitudes')

    def test_func(self):
        licencia = self.get_object()
        return self.request.user.rol in ['GG', 'JI', 'JD'] and licencia.usuario != self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.get_object().usuario
        return context

    def form_valid(self, form):
        licencia = self.get_object()
        usuario = licencia.usuario

        if form.instance.estado == 'A':
            form.instance.aprobado_por = self.request.user
            messages.success(self.request, f"La licencia ha sido marcada como {form.instance.get_estado_display()}.")
        elif form.instance.estado == 'R':
            messages.warning(self.request, f"La licencia ha sido marcada como {form.instance.get_estado_display()}.")
        elif form.instance.estado == 'P':
            messages.info(self.request, f"La licencia ha sido marcada como {form.instance.get_estado_display()}.")

        fecha_ajustada = now() - timedelta(hours=6)
        year = fecha_ajustada.year
        estados = {
            'A': "Aprobada",
            'R': "Rechazada",
            'P': "Pendiente",
        }
        context = {
            "usuario": usuario.first_name,
            "tipo": licencia.get_tipo_display(),
            "fecha_inicio": licencia.fecha_inicio,
            "fecha_fin": licencia.fecha_fin,
            "estado": estados.get(form.instance.estado, "Desconocido"),
            "aprobado_por": self.request.user.get_full_name(),
            "year": year,
            "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
            "enlace_revisar": settings.ENLACE_DEV,
        }

        html_content = render_to_string("mail_estado_licencia.html", context)
        email_sender = MicrosoftGraphEmail()
        subject = f"Tu licencia ha sido {context['estado']}"

        try:
            email_sender.send_email(
                subject=subject,
                content=html_content,
                to_recipients=[usuario.email],
            )
        except Exception as e:
            print(f"Error al enviar correo al usuario {usuario.email}: {e}")

        return super().form_valid(form)



class EditarLicenciaView(UpdateView):
    model = Licencia
    form_class = LicenciaForm
    template_name = 'editar_licencia.html'
    success_url = reverse_lazy('mis_licencias')

    def calcular_fecha_lactancia(self, fecha_inicio):
        fecha_final = fecha_inicio + relativedelta(months=6)
        fecha_final = fecha_final.replace(hour=fecha_inicio.hour + 1, minute=0, second=0)
        return fecha_final

    def calcular_fecha_matrimonio(self, fecha_inicio):
        fecha_actual = fecha_inicio.date()
        total_dias = 0

        while total_dias < 3:
            if fecha_actual.weekday() < 5 and not FeriadoNacional.objects.filter(fecha=fecha_actual).exists():
                total_dias += 1
                if total_dias == 3:
                    break
            fecha_actual += timedelta(days=1)

        return datetime.combine(fecha_actual, time(23, 59, 59))

    def calcular_horas_calamidad(self, fecha_inicio, fecha_fin):

        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )
        horas_totales = Decimal(0)
        fecha_actual = fecha_inicio.date()
        tz = get_current_timezone()

        while fecha_actual <= fecha_fin.date():
            if (fecha_actual.weekday() < 5 and 
                fecha_actual not in [feriado.fecha for feriado in feriados]):

                inicioDia = make_aware(datetime.combine(fecha_actual, time(7, 0)), tz)
                finDia = make_aware(datetime.combine(fecha_actual, time(17, 0)), tz)

                inicioValido = max(fecha_inicio, inicioDia)
                finValido = min(fecha_fin, finDia)

                if inicioValido < finValido:
                    horasDia = Decimal((finValido - inicioValido).total_seconds() / 3600)

                    almuerzoInicio = make_aware(datetime.combine(fecha_actual, time(12, 0)), tz)
                    almuerzoFin = make_aware(datetime.combine(fecha_actual, time(13, 0)), tz)

                    if inicioValido <= almuerzoInicio < finValido or inicioValido < almuerzoFin <= finValido:
                        horasDia -= Decimal(1)

                    horasDia = min(horasDia, Decimal(9))
                    horas_totales += horasDia

            fecha_actual += timedelta(days=1)

        return horas_totales



    def form_valid(self, form):
        licencia = form.save(commit=False)
        licencia.usuario = self.request.user

        if licencia.tipo == 'LAC':
            almuerzo_inicio = licencia.fecha_inicio.replace(hour=12, minute=0, second=0)
            almuerzo_fin = licencia.fecha_inicio.replace(hour=13, minute=0, second=0)

            if almuerzo_inicio <= licencia.fecha_inicio < almuerzo_fin:
                form.add_error('fecha_inicio', "La hora de inicio no puede ser durante el almuerzo (12:00 - 13:00).")
                return self.form_invalid(form)

            licencia.fecha_fin = self.calcular_fecha_lactancia(licencia.fecha_inicio)
            licencia.horas_totales = 1

        elif licencia.tipo == 'MAT':
            licencia.fecha_inicio = datetime.combine(licencia.fecha_inicio.date(), time(0, 0, 0))
            licencia.fecha_fin = self.calcular_fecha_matrimonio(licencia.fecha_inicio)
            licencia.dias_totales = 3
            licencia.estado = 'P'

        elif licencia.tipo == 'CAL':  # Lógica para Calamidad
            licencia.horas_totales = self.calcular_horas_calamidad(licencia.fecha_inicio, licencia.fecha_fin)
            horas_acumuladas = Licencia.objects.filter(
                usuario=licencia.usuario,
                tipo='CAL',
                fecha_inicio__year=licencia.fecha_inicio.year
            ).exclude(pk=licencia.pk).aggregate(models.Sum('horas_totales'))['horas_totales__sum'] or Decimal(0)

            if Decimal(horas_acumuladas) + licencia.horas_totales > Decimal(135):
                form.add_error('fecha_fin', "No puedes exceder las 135 horas anuales para Calamidad Doméstica.")
                return self.form_invalid(form)

        licencia.save()
        messages.success(self.request, "La licencia ha sido actualizada correctamente.")

        jefe = self.request.user.jefe
        if jefe and jefe.email:
            fecha_ajustada = now() - timedelta(hours=6)
            year = fecha_ajustada.year
            context = {
                "jefe": jefe.first_name,
                "usuario": self.request.user.get_full_name(),
                "tipo": form.instance.get_tipo_display(),
                "fecha_inicio": licencia.fecha_inicio,
                "fecha_fin": licencia.fecha_fin,
                "descripcion": form.instance.descripcion,
                "year": year,
                "url_imagen": "https://itrecursos.s3.amazonaws.com/FALCON+2-02.png",
                "enlace_revisar":settings.ENLACE_DEV 
            }

            html_content = render_to_string("mail_editar_licencia.html", context)
            email_sender = MicrosoftGraphEmail()
            subject = "Edición de licencia registrada"
            content=html_content

            try:
                email_sender.send_email(
                    subject=subject,
                    content=content,
                    to_recipients=[jefe.email],
                )
            except Exception as e:
                print(f"Error al enviar correo al jefe {jefe.email}: {e}")

        return super().form_valid(form)


class EliminarLicenciaView(DeleteView):
    model = Licencia
    template_name = 'confirmar_eliminacion_licencia.html'
    success_url = reverse_lazy('mis_licencias')

    def delete(self, request, *args, **kwargs):
        licencia = self.get_object()
        if not licencia.es_eliminable():
            messages.error(request, "No puedes eliminar una licencia con fecha de inicio pasada.")
            return redirect('mis_licencias')
        messages.success(request, "La licencia ha sido eliminada correctamente.")
        return super().delete(request, *args, **kwargs)

@login_required
def reporte_licencias(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")
    
    licencias = Licencia.objects.filter(
        estado_cierre=False,
        estado='A'
    ).order_by('usuario', 'fecha_inicio')

    licencias_por_usuario = {}
    for licencia in licencias:
        usuario = licencia.usuario
        if usuario not in licencias_por_usuario:
            licencias_por_usuario[usuario] = {'licencias': [], 'total_dias': 0, 'total_horas': 0}
        
        licencias_por_usuario[usuario]['licencias'].append(licencia)
        licencias_por_usuario[usuario]['total_dias'] += licencia.dias_totales or 0
        licencias_por_usuario[usuario]['total_horas'] += licencia.horas_totales or 0

    hay_licencias_pendientes = licencias.exists()

    if request.method == "POST":
        seleccionados = request.POST.getlist('seleccionados')
        if 'marcar_cerrado' in request.POST:
            if seleccionados:
                licencias_actualizadas = Licencia.objects.filter(id__in=seleccionados).update(estado_cierre=True)
                messages.success(request, f"{licencias_actualizadas} licencias han sido marcadas como cerradas.")
                return redirect('reporte_licencias')
            else:
                messages.warning(request, "Por favor selecciona al menos una licencia para marcar como cerrada.")
        
        elif 'generar_reporte' in request.POST:
            request.session['reporte_licencias'] = seleccionados
            return redirect('generar_reporte_licencias_pdf')

    paginator = Paginator(list(licencias_por_usuario.items()), 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reporte_licencias.html', {
        'page_obj': page_obj,
        'hay_licencias_pendientes': hay_licencias_pendientes,
        'fecha_reporte': now(),
    })


@login_required
def generar_reporte_licencias_pdf(request):
    if not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    licencias = Licencia.objects.filter(estado='A', estado_cierre=False).order_by('usuario', 'fecha_inicio')

    licencias_por_usuario = {}
    for licencia in licencias:
        usuario = licencia.usuario
        if usuario not in licencias_por_usuario:
            licencias_por_usuario[usuario] = {
                'licencias': [],
                'total_dias': 0,
                'total_horas': 0,
            }
        licencias_por_usuario[usuario]['licencias'].append(licencia)
        if licencia.dias_totales:
            licencias_por_usuario[usuario]['total_dias'] += licencia.dias_totales
        if licencia.horas_totales:
            licencias_por_usuario[usuario]['total_horas'] += licencia.horas_totales

    context = {
        'licencias_por_usuario': licencias_por_usuario,
        'fecha_reporte': now(),
    }

    template = get_template('reporte_licencias_pdf.html')
    html = template.render(context)
    fecha_actual = datetime.now().strftime("%Y:%m:%d")
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_licencias_{fecha_actual}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response, encoding='UTF-8')

    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=400)

    return response




def convertir_dias_a_horas(usuario, dias_a_convertir):
    # Calcular días disponibles del usuario
    dias_disponibles_data = calcular_dias_disponibles(usuario)
    dias_disponibles = dias_disponibles_data['dias_disponibles']

    if dias_a_convertir <= 0:
        raise ValueError("La cantidad de días a convertir debe ser mayor a cero.")
    if dias_a_convertir > dias_disponibles:
        raise ValueError("No puedes convertir más días de los disponibles.")

    # Calcular horas compensatorias (9 horas por día)
    horas_compensatorias = Decimal(dias_a_convertir) * Decimal(9)

    # Registrar la conversión en el modelo
    conversion = ConversionVacacionesHoras.objects.create(
        usuario=usuario,
        dias_convertidos=dias_a_convertir,
        horas_compensatorias=horas_compensatorias
    )

    # Actualizar el cálculo de horas compensatorias
    return conversion


def convertir_vacaciones_a_horas_view(request):
    if request.method == 'POST':
        try:
            dias_a_convertir = int(request.POST.get('dias_a_convertir', 0))  # Convertir a entero

            if dias_a_convertir <= 0:
                raise ValueError("La cantidad de días debe ser un número entero mayor a cero.")

            conversion = convertir_dias_a_horas(request.user, dias_a_convertir)
            messages.success(request, f"Has convertido {conversion.dias_convertidos} días a {conversion.horas_compensatorias} horas compensatorias.")
            
            # Redirigir al dashboard después de una conversión exitosa
            return redirect(reverse_lazy('dashboard'))
        except ValueError as e:
            messages.error(request, str(e))

    dias_disponibles = calcular_dias_disponibles(request.user)['dias_disponibles']
    return render(request, 'convertir_vacaciones.html', {'dias_disponibles': dias_disponibles})