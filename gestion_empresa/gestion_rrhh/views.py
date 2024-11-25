from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View, DeleteView
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
from django.db.models import Q

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
    # Inicialización de los tipos
    tipos = ['HE', 'HC']  # Trabajamos con HE y HC base
    horas_por_tipo = {'HE': 0, 'HC': 0}

    # Calcular horas de HE y HC del modelo RegistroHoras
    for tipo in tipos:
        total_horas = RegistroHoras.objects.filter(
            usuario=usuario,
            tipo=tipo,
            estado='A'
        ).aggregate(Sum('horas'))['horas__sum'] or 0
        horas_por_tipo[tipo] = total_horas

    # Manejar HEF (sumar a HE y HC según corresponda)
    horas_hef = RegistroHoras.objects.filter(
        usuario=usuario,
        tipo='HEF',
        estado='A'
    ).aggregate(
        total_horas=Sum('horas'),
        horas_compensatorias_feriado=Sum('horas_compensatorias_feriado')
    )

    # Sumar horas de HEF a HE
    horas_por_tipo['HE'] += horas_hef['total_horas'] or 0

    # Sumar horas compensatorias feriado de HEF a HC
    horas_por_tipo['HC'] += horas_hef['horas_compensatorias_feriado'] or 0

    # Restar horas de solicitudes aprobadas de tipo HC
    horas_solicitudes_hc = Solicitud.objects.filter(
        usuario=usuario,
        tipo='HC',
        estado='A'  # Solo solicitudes aprobadas
    ).aggregate(Sum('horas'))['horas__sum'] or 0

    # Restar las horas aprobadas del modelo Solicitud
    horas_por_tipo['HC'] -= horas_solicitudes_hc

    return horas_por_tipo


@login_required
def dashboard(request):
    usuario = request.user
    fecha_actual = now().date()
    fecha_limite = fecha_actual + timedelta(days=10)
    dias_data = calcular_dias_disponibles(usuario)
    dias_disponibles = dias_data['dias_disponibles']
    horas_data = calcular_horas_individuales(usuario)
    horas_extra = horas_data['HE']
    horas_compensatorias = horas_data['HC']

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

        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
            fecha_inicio__date=fecha_inicio.date(),

        )
        for solicitud in solicitudes_en_conflicto:
            print(f"Conflicto con solicitud: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
            if not (fecha_fin <= solicitud.fecha_inicio or fecha_inicio >= solicitud.fecha_fin):
                form.add_error(None, "Ya tienes una solicitud que se solapa con este rango de horas.")
                return self.form_invalid(form)

        
        if tipo_solicitud == 'V':
            dias_solicitados = (fecha_fin.date() - fecha_inicio.date()).days +1
            form.instance.dias_solicitados = dias_solicitados

            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles} días disponibles."
                )

        elif tipo_solicitud == 'HC':
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600

            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)
            
            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)
            
            form.instance.horas = horas_solicitadas
        
        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        messages.success(self.request, 'Solicitud creada correctamente y pendiente de aprobación.')
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
        return super().form_valid(form)

class EditarMiSolicitudView(LoginRequiredMixin, UpdateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = 'editar_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_initial(self):
        initial = super().get_initial()
        # Cargar las horas actuales si existen
        if self.object.horas:
            initial['horas'] = self.object.horas
        return initial

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        tipo_solicitud = self.object.tipo  # El tipo ya está definido en el registro
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        usuario = self.request.user
        dias_data = calcular_dias_disponibles(usuario)
        dias_disponibles = dias_data['dias_disponibles']
        horas_data = calcular_horas_individuales(usuario)
        horas_compensatorias = horas_data['HC']
        
        solicitudes_en_conflicto = Solicitud.objects.filter(
            usuario=usuario,
            fecha_inicio__date=fecha_inicio.date(),
        ).exclude(id=self.object.id)  # Excluir la misma solicitud si es una edición
        for solicitud in solicitudes_en_conflicto:
            print(f"Conflicto con solicitud: ID {solicitud.id}, Inicio {solicitud.fecha_inicio}, Fin {solicitud.fecha_fin}")
            if not (fecha_fin <= solicitud.fecha_inicio or fecha_inicio >= solicitud.fecha_fin):
                form.add_error(None, "Ya tienes una solicitud que se solapa con este rango de horas.")
                return self.form_invalid(form)

        if tipo_solicitud == 'V':
            dias_solicitados = (fecha_fin.date() - fecha_inicio.date()).days + 1
            form.instance.dias_solicitados = dias_solicitados

            if dias_solicitados > dias_disponibles:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles} días disponibles."
                )

        elif tipo_solicitud == 'HC':
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600

            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)

            if horas_solicitadas > horas_compensatorias:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {horas_compensatorias}).")
                return self.form_invalid(form)

            form.instance.horas = horas_solicitadas

        messages.success(self.request, 'Solicitud actualizada correctamente.')
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
    template_name = 'confirmar_eliminar.html'
    success_url = reverse_lazy('mis_solicitudes')

    def test_func(self):
        solicitud = self.get_object()
        # Solo permite la eliminación si la solicitud pertenece al usuario actual y está pendiente
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

        registros_en_conflicto = RegistroHoras.objects.filter(
            usuario=usuario,
            fecha_inicio__date=fecha_inicio.date(),
        )
        for registro in registros_en_conflicto:
            print(f"Conflicto con sel registro: ID {registro.id}, Inicio {registro.fecha_inicio}, Fin {registro.fecha_fin}")
            if not (fecha_fin <= registro.fecha_inicio or fecha_inicio >= registro.fecha_fin):
                form.add_error(None, "Ya tienes un registro de horas que se solapa con este rango. Por favor, selecciona otro rango")
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

        # Calcular la diferencia de días
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
        return super().form_valid(form)


class EditarMiRegistroHorasView(LoginRequiredMixin, UpdateView):
    model = RegistroHoras
    form_class = RegistrarHorasForm
    template_name = 'editar_registro_horas.html'
    success_url = reverse_lazy('mis_solicitudes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        # Agregar información adicional al contexto
        horas_data = calcular_horas_individuales(usuario)
        context.update({
            'horas_extra': horas_data['HE'],
            'horas_compensatorias': horas_data['HC'],
        })
        return context

    def form_valid(self, form):
        registro = self.get_object()
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')

        # Verificar conflictos de fechas
        registros_en_conflicto = RegistroHoras.objects.filter(
            usuario=registro.usuario,
            fecha_inicio__date=fecha_inicio.date(),
        ).exclude(id=registro.id)

        for r in registros_en_conflicto:
            if not (fecha_fin <= r.fecha_inicio or fecha_inicio >= r.fecha_fin):
                form.add_error(None, "Ya existe un registro en este rango de fechas y horas.")
                return self.form_invalid(form)

        messages.success(self.request, f"El registro de horas {registro.numero_registro} ha sido actualizado.")
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

    # Usar Paginator para dividir los datos
    paginator = Paginator(list(registros_por_usuario.items()), 5)  # Cambia 5 por el número de usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'registros_por_usuario': page_obj,  # Pasar solo la página actual
        'total_horas': sum(user_data['total_horas'] for user_data in registros_por_usuario.values()),
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



@login_required
def lista_incapacidades(request):
    incapacidades = Incapacidad.objects.all().order_by('-fecha_inicio')

    # Configuración del paginador
    paginator = Paginator(incapacidades, 8) 
    page_number = request.GET.get('page')  
    page_obj = paginator.get_page(page_number)  

    return render(request, 'lista_incapacidades.html', {
        'page_obj': page_obj, 
    })


def logout_view(request):
    logout(request)
    return redirect('login')