from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View
from .models import Usuario, Solicitud, HistorialVacaciones, AjusteVacaciones
from .forms import UsuarioCreationForm, SolicitudForm, RegistrarHorasForm,RegistroHorasFilterForm
from django.contrib import messages
from django.contrib.auth import logout
from .models import RegistroHoras
from operator import attrgetter
from django.core.paginator import Paginator
from datetime import date
from .forms import AjusteVacacionesForm
from django.db.models import Sum
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.http import HttpResponse
from django.utils import timezone
import locale
from django.contrib.auth.views import PasswordChangeView
from django.utils.timezone import now, timedelta
from .models import Solicitud
import json
from .models import Incapacidad
from .forms import IncapacidadForm

@login_required
def dashboard(request):
    usuario = request.user
    fecha_actual = now().date()
    fecha_limite = fecha_actual + timedelta(days=10)

    # Calcular días disponibles
    total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
    total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
    total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
    dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados

    # Consultar solicitudes aprobadas (Vacaciones y Horas Compensatorias)
    solicitudes_aprobadas = Solicitud.objects.filter(
        estado='A',
        fecha_inicio__lte=fecha_limite,
        fecha_fin__gte=fecha_actual
    ).values('usuario__first_name', 'usuario__last_name', 'fecha_inicio', 'fecha_fin', 'tipo')

    # Consultar incapacidades aprobadas en el rango de fechas
    incapacidades_aprobadas = Incapacidad.objects.filter(
       
        fecha_inicio__lte=fecha_limite,
        fecha_fin__gte=fecha_actual
    ).values('usuario__first_name', 'usuario__last_name', 'fecha_inicio', 'fecha_fin')

    eventos = []

    # Agregar eventos de solicitudes
    for solicitud in solicitudes_aprobadas:
        nombre_completo = f"{solicitud['usuario__first_name']} {solicitud['usuario__last_name']}"
        if solicitud['tipo'] == 'V':
            title = f"{nombre_completo} (Vacaciones)"
            description = f'Inicio: {solicitud["fecha_inicio"].strftime("%Y-%m-%d")} - Fin: {solicitud["fecha_fin"].strftime("%Y-%m-%d")}'
            start = solicitud['fecha_inicio'].strftime("%Y-%m-%d") 
            end = (solicitud['fecha_fin'] + timedelta(days=1)).strftime("%Y-%m-%d")
            color = "#e74c3c"  # Rojo para vacaciones
        else:  # Horas compensatorias
            title = f"{nombre_completo} (HC)"
            description = f"Inicio: {solicitud['fecha_inicio'].strftime('%H:%M')} - Fin: {solicitud['fecha_fin'].strftime('%H:%M')}"
            start = solicitud['fecha_inicio'].strftime("%Y-%m-%d")
            end = solicitud['fecha_fin'].strftime("%Y-%m-%d")
            color = "#f39c12"  # Naranja para HC

        eventos.append({
            "title": title,
            "start": start,
            "end": end,
            "description": description,
            "color": color
        })

    # Agregar eventos de incapacidades
    for incapacidad in incapacidades_aprobadas:
        nombre_completo = f"{incapacidad['usuario__first_name']} {incapacidad['usuario__last_name']}"
        title = f"{nombre_completo} (Incapacidad)"
        description = f'Inicio: {incapacidad["fecha_inicio"].strftime("%Y-%m-%d")} - Fin: {incapacidad["fecha_fin"].strftime("%Y-%m-%d")}'
        start = incapacidad['fecha_inicio'].strftime("%Y-%m-%d")
        end = (incapacidad['fecha_fin'] + timedelta(days=1)).strftime("%Y-%m-%d")
        color = "#9b9b9b"  # Rojo oscuro para incapacidad

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
        'eventos': json.dumps(eventos),
    }
    return render(request, 'dashboard.html', context)



def PerfilUsuario(request):
    usuario = request.user
    total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
    total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
    total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
    dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
    
    context = {
    'user': usuario,
    'dias_vacaciones_disponibles': dias_disponibles,

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
        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
            fecha_inicio__lte=fecha_fin,
            fecha_fin__gte=fecha_inicio
        )
        if solicitudes_en_conflicto.exists():
            print("entraaa")
            form.add_error(None, "Ya tienes una solicitud de horas que se solapa con este rango. Por favor, selecciona otro rango.")
            return self.form_invalid(form)

        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
        # Calcula el total de días disponibles incluyendo los ajustes
        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
    
        
        if tipo_solicitud == 'V':
            dias_solicitados = (fecha_fin.date() - fecha_inicio.date()).days + 1
            form.instance.dias_solicitados = dias_solicitados
            
            dias_disponibles_totales = dias_disponibles
            if dias_solicitados > dias_disponibles_totales:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles_totales} días disponibles."
                )
                return self.form_invalid(form)

        elif tipo_solicitud == 'HC':
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600

            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)
            
            if horas_solicitadas > self.request.user.horas_compensatorias_disponibles:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {self.request.user.horas_compensatorias_disponibles}).")
                return self.form_invalid(form)
            
            form.instance.horas = horas_solicitadas
        
        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        messages.success(self.request, 'Solicitud creada correctamente y pendiente de aprobación.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
        # Calcula el total de días disponibles incluyendo los ajustes
        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados

        dias_vacaciones = dias_disponibles

        context.update({
            'usuario': usuario,
            'dias_vacaciones': dias_vacaciones,
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
        usuario = self.request.user
        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
        
        if form.instance.estado == 'A':
            if solicitud.tipo == 'V':
                dias_disponibles_totales = total_dias_asignados - total_dias_tomados + total_dias_ajustados

                if solicitud.dias_solicitados > dias_disponibles_totales:
                    dias_faltantes = solicitud.dias_solicitados - dias_disponibles_totales
                    messages.warning(
                        self.request, 
                        f"Advertencia: Al aprobar esta solicitud, el saldo de días de vacaciones será negativo en {dias_faltantes} días."
                    )
                    return self.form_invalid(form)
                dias_por_restar = solicitud.dias_solicitados
                historial_vacaciones = HistorialVacaciones.objects.filter(usuario=solicitud.usuario).order_by('año')
                
                for registro in historial_vacaciones:
                    dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
                    if dias_por_restar <= dias_disponibles:
                        registro.dias_tomados += dias_por_restar
                        registro.save()
                        break
                    else:
                        registro.dias_tomados += dias_disponibles
                        dias_por_restar -= dias_disponibles
                        registro.save()

            elif solicitud.tipo == 'HC':
                if solicitud.usuario.horas_compensatorias_disponibles >= solicitud.horas:
                    solicitud.usuario.horas_compensatorias_disponibles -= solicitud.horas
                    solicitud.usuario.save()  
                else:
                    messages.error(self.request, "No se puede aprobar. El usuario no tiene suficientes horas compensatorias.")
                    return self.form_invalid(form)

            elif solicitud.tipo == 'HE':  # Horas Extra
                if solicitud.usuario.horas_extra_acumuladas >= solicitud.horas:
                    solicitud.usuario.horas_extra_acumuladas -= solicitud.horas
                    solicitud.usuario.save()
                else:
                    messages.error(self.request, "No se puede aprobar. El usuario no tiene suficientes horas extra.")
                    return self.form_invalid(form)

        # Asignar el aprobador
        form.instance.aprobado_por = self.request.user
        messages.success(self.request, 'La solicitud ha sido procesada exitosamente.')
        return super().form_valid(form)


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
        registros_en_conflicto = RegistroHoras.objects.filter(
            usuario=usuario,
            fecha_inicio__lte=fecha_fin, 
            fecha_fin__gte=fecha_inicio 
        )
        if registros_en_conflicto.exists():
            form.add_error(None, "Ya tienes un registro de horas que se solapa con este rango. Por favor, selecciona otro rango.")
            return self.form_invalid(form)

        if rol_usuario == 'IN' and tipo_horas == 'HE':
            form.add_error(None, "Los ingenieros no pueden registrar horas extra.")
            return self.form_invalid(form)
        
        if rol_usuario == 'TE' and tipo_horas == 'HEF':
            form.add_error(None, "Los Técnicos no pueden registrar horas extra para dias feriados.")
            return self.form_invalid(form)

        elif rol_usuario in ['GG', 'JI', 'JD'] and tipo_horas == 'HE':
            form.add_error(None, "Los gerentes o jefes no pueden registrar horas extra.")
            return self.form_invalid(form)
        form.instance.numero_registro = form.cleaned_data['numero_registro']
        messages.success(self.request, 'Registro de horas creado y pendiente de aprobación.')
        return super().form_valid(form)


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

        # Calcular la diferencia de días
        diferencia_dias = (registro.fecha_fin.date() - registro.fecha_inicio.date()).days + 1
        print(f"Diferencia de días: {diferencia_dias} días")

        if form.instance.estado == 'A':  
            if registro.tipo == 'HE':
                registro.usuario.horas_extra_acumuladas += registro.horas
                print(f"Horas extra después: {registro.usuario.horas_extra_acumuladas}")
            elif registro.tipo == 'HC':
                registro.usuario.horas_compensatorias_disponibles += registro.horas
                print(f"Horas compensatorias después: {registro.usuario.horas_compensatorias_disponibles}")
            elif registro.tipo =='HEF':
                registro.usuario.horas_extra_acumuladas+=registro.horas
                registro.usuario.horas_compensatorias_disponibles = registro.usuario.horas_compensatorias_disponibles + 9 * diferencia_dias
            registro.usuario.save()

        form.instance.aprobado_por = self.request.user
        messages.success(self.request, 'El registro de horas ha sido procesado exitosamente.')
        return super().form_valid(form)


class ListaSolicitudesRegistrosPendientesView(ListView):
    template_name = 'lista_solicitudes.html'
    context_object_name = 'pendientes'

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


class HistorialCombinadoView(ListView):
    template_name = 'historial_solicitudes.html'
    context_object_name = 'registros_y_solicitudes'
    
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

        # Combinar ambos querysets en una lista
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
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)

        return context


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
    if request.user.rol not in ['GG', 'JI', 'JD']:
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('dashboard')

    usuarios = Usuario.objects.filter(is_superuser=False)
    usuarios_vacaciones = []

    for usuario in usuarios:
        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0

        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
        
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
            ajuste.año = date.today().year 
            ajuste.save()

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
def reporte_horas_extra(request):
    registros = RegistroHoras.objects.filter(
        tipo='HE',
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

    total_horas = sum(user_data['total_horas'] for user_data in registros_por_usuario.values())

    context = {
        'registros_por_usuario': registros_por_usuario,
        'total_horas': total_horas,
    }
    return render(request, 'reporte_horas_extra.html', context)


@login_required
def cerrar_quincena(request):
    registros_a_pagar = RegistroHoras.objects.filter(
        tipo='HE',
        estado='A',
        estado_pago='NP'
    )

    for registro in registros_a_pagar:
        usuario = registro.usuario  
        usuario.horas_extra_acumuladas =0 
        usuario.save()

    registros_actualizados = registros_a_pagar.update(estado_pago='PG')

    messages.success(request, f"{registros_actualizados} registros de horas extra han sido marcados como pagados.")
    return redirect('reporte_horas_extra')



class GenPdf(View):
    def get(self, request, *args, **kwargs):
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
            except:
                pass

        registros = RegistroHoras.objects.filter(
            tipo='HE',
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
        }

        template = get_template('reporte_horas_extra_pdf.html')
        html = template.render(context)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_horas_extra.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response, encoding='UTF-8')

        if pisa_status.err:
            return HttpResponse('Error al generar el PDF', status=400)
        return response



class CrearIncapacidadView(LoginRequiredMixin, CreateView):
    model = Incapacidad
    form_class = IncapacidadForm
    template_name = 'crear_incapacidad.html'
    success_url = reverse_lazy('lista_incapacidades')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
         # Verificar fechas conflictivas
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user


        # Verificar fechas conflictivas
        conflictos = Incapacidad.objects.filter(
            usuario=usuario,
            fecha_inicio__lte=fecha_fin,
            fecha_fin__gte=fecha_inicio
        )
        if conflictos.exists():
            form.add_error(None, "Ya tienes una incapacidad registrada para este rango de fechas.")
            return self.form_invalid(form)
        
        # Verificar si el archivo fue adjuntado
        if not form.cleaned_data.get('archivo_adjunto'):
            form.add_error('archivo', "Debes adjuntar un archivo.")
            return self.form_invalid(form)
        return super().form_valid(form)


class ListaIncapacidadesView(LoginRequiredMixin, ListView):
    model = Incapacidad
    template_name = 'lista_incapacidades.html'
    context_object_name = 'incapacidades'

    def get_queryset(self):
        # Mostrar las incapacidades solo para el jefe
        if self.request.user.rol in ['GG', 'JI', 'JD']:
            return Incapacidad.objects.filter(usuario__jefe=self.request.user)
        return Incapacidad.objects.filter(usuario=self.request.user)





def logout_view(request):
    logout(request)
    return redirect('login')