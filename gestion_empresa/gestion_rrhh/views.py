from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View, DeleteView
from .models import FeriadoNacional, Usuario, Solicitud, HistorialVacaciones, AjusteVacaciones, RegistroHoras,Solicitud, Incapacidad
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



def es_jefe(user):
    return user.rol in ['GG', 'JI', 'JD']

def calcular_dias_disponibles(usuario):
    total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
    total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
    total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
    dias_disponibles = total_dias_asignados + total_dias_ajustados - total_dias_tomados 
    return {
        'total_asignados': total_dias_asignados,
        'total_tomados': total_dias_tomados,
        'total_ajustados': total_dias_ajustados,
        'dias_disponibles': dias_disponibles
    }

def calcular_horas_individuales(usuario):
    tipos = ['HE', 'HC']  # Trabajamos con HE y HC base
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
    return horas_por_tipo

@login_required
def dashboard(request):
    usuario = request.user
    fecha_actual = now().date()
    # fecha_limite = fecha_actual + timedelta(days=30)
    dias_data = calcular_dias_disponibles(usuario)
    dias_disponibles = dias_data['dias_disponibles']
    horas_data = calcular_horas_individuales(usuario)
    horas_extra = horas_data['HE']
    horas_compensatorias = horas_data['HC']

    solicitudes_aprobadas = Solicitud.objects.filter(
        estado='A',

        fecha_fin__gte=fecha_actual
    ).values('usuario__first_name', 'usuario__last_name', 'fecha_inicio', 'fecha_fin', 'tipo')
    incapacidades_aprobadas = Incapacidad.objects.filter(
        fecha_fin__gte=fecha_actual
    ).values('usuario__first_name', 'usuario__last_name', 'fecha_inicio', 'fecha_fin')
    eventos = []

    for solicitud in solicitudes_aprobadas:
        nombre_completo = f"{solicitud['usuario__first_name']} {solicitud['usuario__last_name']}"
        if solicitud['tipo'] == 'V':
            title = f"{nombre_completo} (Vacaciones)"
            description = f'Inicio: {solicitud["fecha_inicio"].strftime("%Y-%m-%d")} - Fin: {solicitud["fecha_fin"].strftime("%Y-%m-%d")}'
            start = solicitud['fecha_inicio'].strftime("%Y-%m-%d") 
            end = (solicitud['fecha_fin'] + timedelta(days=1)).strftime("%Y-%m-%d")
            color = "#e74c3c"
        else:
            title = f"{nombre_completo} (HC)"
            description = f"Inicio: {solicitud['fecha_inicio'].strftime('%H:%M')} - Fin: {solicitud['fecha_fin'].strftime('%H:%M')}"
            start = solicitud['fecha_inicio'].strftime("%Y-%m-%d")
            end = solicitud['fecha_fin'].strftime("%Y-%m-%d")
            color = "#f39c12"
        eventos.append({
            "title": title,
            "start": start,
            "end": end,
            "description": description,
            "color": color
        })

    for incapacidad in incapacidades_aprobadas:
        nombre_completo = f"{incapacidad['usuario__first_name']} {incapacidad['usuario__last_name']}"
        title = f"{nombre_completo} (Incapacidad)"
        description = f'Inicio: {incapacidad["fecha_inicio"].strftime("%Y-%m-%d")} - Fin: {incapacidad["fecha_fin"].strftime("%Y-%m-%d")}'
        start = incapacidad['fecha_inicio'].strftime("%Y-%m-%d")
        end = (incapacidad['fecha_fin'] + timedelta(days=1)).strftime("%Y-%m-%d")
        color = "#9b9b9b"

        eventos.append({
            "title": title,
            "start": start,
            "end": end,
            "description": description,
            "color": color
        })

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

class CambiarContrasenaView(PasswordChangeView):
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
    
class CrearSolicitudView(LoginRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = 'crear_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        last_record = Solicitud.objects.order_by('id').last()
        if last_record:
            numero_solicitud = last_record.id + 1 
        else:
            numero_solicitud = 1 
        
        initial['numero_solicitud'] = f"S-{numero_solicitud:04d}"
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

        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )


        non_working_dates = [
            date for date in (fecha_inicio.date() + timedelta(n) for n in range((fecha_fin.date() - fecha_inicio.date()).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
        ]

        if non_working_dates:
            non_working_str = ", ".join(date.strftime("%d/%m/%Y (%A)") for date in non_working_dates)
            form.add_error(None, f"La solicitud incluye días no laborables: {non_working_str}. Por favor, selecciona otro rango.")
            return self.form_invalid(form)
        

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

            fecha_inicio=fecha_inicio.date()
            fecha_fin=fecha_fin.date()
            dias_solicitados = (fecha_fin - fecha_inicio).days +1
            form.instance.dias_solicitados = dias_solicitados

            fecha_actual = date.today()

            if fecha_inicio<fecha_actual:
                form.add_error(None, "Imposible solicitar vacaciones para fechas menores a la actual.")
                return self.form_invalid(form)


            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles} días disponibles."
                )

        elif tipo_solicitud == 'HC':
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600
            tz = get_current_timezone()
            almuerzo_inicio = make_aware(datetime.combine(fecha_inicio.date(), time(12, 0)), tz)
            almuerzo_fin = make_aware(datetime.combine(fecha_inicio.date(), time(13, 0)), tz)

            if fecha_inicio < almuerzo_fin and fecha_fin > almuerzo_inicio:
                horas_solicitadas -= 1

            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)
            
            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)
            
            form.instance.horas = horas_solicitadas
        
        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        messages.success(self.request, 'Solicitud creada correctamente y pendiente de aprobación.')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            year = now().year
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

    def test_func(self):
        solicitud = self.get_object()

        if solicitud.usuario == self.request.user:
            messages.error(self.request, 'No puedes aprobar o rechazar tu propia solicitud.')
            return False

        if self.request.user.is_superuser or self.request.user.rol == 'GG':
            return True
        elif self.request.user.rol == 'JI':
            return solicitud.usuario.departamento.nombre in ['IT', 'ENERGIA', 'INDUSTRIA', 'TALLER']
        elif self.request.user.rol == 'JD':
            return solicitud.usuario in self.request.user.subordinados.all()
        return False

    def form_valid(self, form):
        solicitud = self.get_object()
        dias_data = calcular_dias_disponibles(solicitud.usuario)
        usuario = solicitud.usuario
        dias_disponibles = dias_data['dias_disponibles']
        año_actual = now().year
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
        year = now().year
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


        feriados = FeriadoNacional.objects.filter(
            fecha__range=[fecha_inicio.date(), fecha_fin.date()]
        )


        non_working_dates = [
            date for date in (fecha_inicio.date() + timedelta(n) for n in range((fecha_fin.date() - fecha_inicio.date()).days + 1)) 
            if date.weekday() >= 5 or date in [feriado.fecha for feriado in feriados]
        ]

        if non_working_dates:
            non_working_str = ", ".join(date.strftime("%d/%m/%Y (%A)") for date in non_working_dates)
            form.add_error(None, f"La solicitud incluye días no laborables: {non_working_str}. Por favor, selecciona otro rango.")
            return self.form_invalid(form)
        
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
            fecha_inicio=fecha_inicio.date()
            fecha_fin=fecha_fin.date()
            form.instance.descripcion="Vacaciones"
            dias_solicitados = (fecha_fin- fecha_inicio).days + 1
            form.instance.dias_solicitados = dias_solicitados

            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles} días disponibles."
                )

        elif tipo_solicitud == 'HC':
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600

            tz = get_current_timezone()
            almuerzo_inicio = make_aware(datetime.combine(fecha_inicio.date(), time(12, 0)), tz)
            almuerzo_fin = make_aware(datetime.combine(fecha_inicio.date(), time(13, 0)), tz)

            if fecha_inicio < almuerzo_fin and fecha_fin > almuerzo_inicio:
                horas_solicitadas -= 1

            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)

            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)

            form.instance.horas = horas_solicitadas

        messages.success(self.request, 'Solicitud actualizada correctamente.')

        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            year = now().year
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
            'horas_extra': horas_extra,
            'horas_compensatorias': horas_compensatorias,
        })
        return context


class EliminarMiSolicitudView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Solicitud
    template_name = 'confirmar_eliminar_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

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
        last_record = RegistroHoras.objects.order_by('id').last()
        if last_record:
            numero_registro = last_record.id + 1 
        else:
            numero_registro = 1 
        
        initial['numero_registro'] = f"RGH-{numero_registro:04d}"
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
            form.add_error(None, "Los Técnicos no pueden registrar horas extra para dias feriados.")
            return self.form_invalid(form)

        elif rol_usuario in ['GG', 'JI', 'JD','IN','ADM'] and tipo_horas == 'HE':
            form.add_error(None, "Usted no puede registrar horas extra.")
            return self.form_invalid(form)
        
        form.instance.numero_registro = form.cleaned_data['numero_registro']


        messages.success(self.request, 'Registro de horas creado y pendiente de aprobación.')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            year = now().year
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

    def form_valid(self, form):
        registro = self.get_object()
        usuario = registro.usuario

        diferencia_dias = (registro.fecha_fin.date() - registro.fecha_inicio.date()).days + 1
        print(f"Diferencia de días: {diferencia_dias} días")

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

        year = now().year
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
                to_recipients=[usuario.email],  # Correo del usuario al que pertenece la solicitud
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
            form.add_error(None, "Los Técnicos no pueden registrar horas extra para dias feriados.")
            return self.form_invalid(form)

        elif rol_usuario in ['GG', 'JI', 'JD','IN','ADM'] and tipo_horas == 'HE':
            form.add_error(None, "Usted no puede registrar horas extra.")
            return self.form_invalid(form)
        
        form.instance.numero_registro = form.cleaned_data['numero_registro']

        messages.success(self.request, f"El registro de horas {registro.numero_registro} ha sido actualizado.")
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            year = now().year
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

        if user.rol in ['GG', 'JI', 'JD']:
            registros_queryset = registros_queryset.filter(usuario__in=user.subordinados.all())
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=user.subordinados.all())
        else:
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()

        pendientes = list(solicitudes_queryset) + list(registros_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3} 
        for item in pendientes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
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
        return subordinados_nivel_1 | subordinados_nivel_2

    def get_queryset(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        registros_queryset = RegistroHoras.objects.filter(estado='P')
        solicitudes_queryset = Solicitud.objects.filter(estado='P')

        if user.rol in ['GG', 'JI', 'JD']:
            subordinados = self.obtener_subordinados_dos_niveles(user)
            registros_queryset = registros_queryset.filter(usuario__in=subordinados)
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=subordinados)
        else:
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()

        pendientes = list(solicitudes_queryset) + list(registros_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}
        for item in pendientes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        pendientes = sorted(pendientes, key=attrgetter('estado_orden', 'fecha_inicio'))

        paginator = Paginator(pendientes, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['pendientes'] = page_obj
        context['page_obj'] = page_obj
        return context



class HistorialCombinadoView(ListView):
    template_name = 'historial_solicitudes.html'
    context_object_name = 'registros_y_solicitudes'
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol not in ['GG', 'JI', 'JD']:
            raise PermissionDenied("No tienes permiso para acceder a esta página.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        estado = self.request.GET.get('estado')
        tipo = self.request.GET.get('tipo')
        usuario_id = self.request.GET.get('usuario')
        registros_queryset = RegistroHoras.objects.filter(usuario__in=user.subordinados.all())
        solicitudes_queryset = Solicitud.objects.filter(usuario__in=user.subordinados.all())

        if estado:
            registros_queryset = registros_queryset.filter(estado=estado)
            solicitudes_queryset = solicitudes_queryset.filter(estado=estado)
        if tipo:
            solicitudes_queryset = solicitudes_queryset.filter(tipo=tipo)
        if usuario_id:
            registros_queryset = registros_queryset.filter(usuario_id=usuario_id)
            solicitudes_queryset = solicitudes_queryset.filter(usuario_id=usuario_id)

        registros_y_solicitudes = list(registros_queryset) + list(solicitudes_queryset)

        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}
        for item in registros_y_solicitudes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        registros_y_solicitudes = sorted(registros_y_solicitudes, key=attrgetter('estado_orden', 'fecha_inicio'))
        paginator = Paginator(registros_y_solicitudes, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['registros_y_solicitudes'] = page_obj
        context['page_obj'] = page_obj
        context['subordinados'] = user.subordinados.all()
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)
        return context
    

@login_required
def reporte_solicitudes(request):
    if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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
    if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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

class MiSolicitudYRegistroView(ListView):
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
    if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
        raise PermissionDenied("No tienes permiso para acceder a esta página.")

    usuarios = Usuario.objects.filter(is_superuser=False)
    usuarios_vacaciones = []

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

            # Enviar correos electrónicos de notificación
            context = {
                'ajustado_por': request.user.get_full_name(),
                'usuario': usuario.get_full_name(),
                'dias_ajustados': ajuste.dias_ajustados,
                'total_dias_disponibles': calcular_dias_disponibles(usuario)['dias_disponibles'],
                'fecha_ajuste': now().strftime('%d/%m/%Y %H:%M'),
            
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

    paginator = Paginator(ajustes, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'historial_ajustes_vacaciones.html', {'page_obj': page_obj})


@login_required
def reporte_horas_extra_html(request):
    # Verificar permisos
    if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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
            messages.success(request, f"{registros_actualizados} registros de horas extra han sido marcados como pagados.")
            return redirect('reporte_horas_extra')

        elif 'generar_reporte' in request.POST:
            request.session['reporte_horas_extra'] = seleccionados
            return redirect('generar_pdf')

    # Paginación
    paginator = Paginator(list(registros_por_usuario.items()), 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reporte_horas_extra.html', {
        'page_obj': page_obj,
        'hay_registros_pendientes': hay_registros_pendientes,
    })



class reporte_horas_extra_PDF(View):
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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
                'fecha_inicio': registro.fecha_inicio.strftime("%#d de %B de %Y a las %H:%M"),
                'fecha_fin': registro.fecha_fin.strftime("%#d de %B de %Y a las %H:%M"),
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
            year = now().year
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


class GenerarReporteIncapacidadesView(View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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
    if request.user.rol != 'JD' or not request.user.departamento or request.user.departamento.nombre != 'ADMON':
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

        form.instance.usuario = self.request.user

        messages.success(self.request, 'Incapacidad actualizada correctamente')
        
        jefe = self.request.user.jefe
        if jefe and jefe.email: 
            year = now().year
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
        return self.request.user.is_superuser  # Solo usuarios con superusuario pueden agregar

class FeriadoNacionalUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = FeriadoNacional
    form_class = FeriadoNacionalForm
    template_name = 'feriados/feriado_form.html'
    success_url = reverse_lazy('feriado_list')

    def test_func(self):
        return self.request.user.is_superuser  # Solo usuarios con superusuario pueden editar

class FeriadoNacionalDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FeriadoNacional
    template_name = 'feriados/feriado_confirm_delete.html'
    success_url = reverse_lazy('feriado_list')

    def test_func(self):
        return self.request.user.is_superuser




    
def logout_view(request):
    logout(request)
    return redirect('login')