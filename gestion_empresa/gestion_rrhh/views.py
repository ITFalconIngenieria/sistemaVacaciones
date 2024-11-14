from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from .models import Usuario, Solicitud, HistorialVacaciones, AjusteVacaciones
from .forms import UsuarioCreationForm, SolicitudForm, RegistrarHorasForm,RegistroHorasFilterForm
from django.contrib import messages
from django.contrib.auth import logout
from .models import RegistroHoras
from django.core.exceptions import ValidationError
from operator import attrgetter
from django.core.paginator import Paginator
from datetime import date
from .forms import AjusteVacacionesForm
from django.db.models import Sum



@login_required
def dashboard(request):
    usuario = request.user
    # Calcula el total de días asignados y tomados considerando todo el historial del usuario
    total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
    total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
    total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
    # Calcula el total de días disponibles incluyendo los ajustes
    dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
    
    context = {
    'user': usuario,
    'dias_vacaciones_disponibles': dias_disponibles,

    }
    return render(request, 'dashboard.html', context)


class CrearUsuarioView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreationForm
    template_name = 'crear_usuario.html'
    success_url = reverse_lazy('dashboard')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.rol in ['GG', 'JI', 'JD']
    

# Solicitud para tomar vacaciones y horas compensatorias
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
        # Calcula el total de días asignados y tomados considerando todo el historial del usuario
        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
        # Calcula el total de días disponibles incluyendo los ajustes
        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
    
        
        if tipo_solicitud == 'V':  # Vacaciones
            dias_solicitados = (fecha_fin.date() - fecha_inicio.date()).days + 1
            form.instance.dias_solicitados = dias_solicitados
            
            # Calcular el total de días disponibles en el historial
            dias_disponibles_totales = dias_disponibles

            # Verificar si hay suficientes días disponibles
            if dias_solicitados > dias_disponibles_totales:
                messages.warning(
                    self.request,
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {dias_disponibles_totales} días disponibles."
                )
                return self.form_invalid(form)

        elif tipo_solicitud == 'HC':  # Horas Compensatorias
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600

            # Verificar si las horas solicitadas exceden el límite de 9 horas
            if horas_solicitadas > 9:
                form.add_error(None, "La cantidad de horas solicitadas excede las 9 horas permitidas.")
                return self.form_invalid(form)
            
            # Verificar si el usuario tiene suficientes horas compensatorias disponibles
            if horas_solicitadas > self.request.user.horas_compensatorias_disponibles:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {self.request.user.horas_compensatorias_disponibles}).")
                return self.form_invalid(form)
            
            # Asignar las horas solicitadas si todo está en orden
            form.instance.horas = horas_solicitadas

        form.instance.numero_solicitud = form.cleaned_data['numero_solicitud']
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        # Calcula el total de días asignados y tomados considerando todo el historial del usuario
        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0
        # Calcula el total de días disponibles incluyendo los ajustes
        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados

        # Obtener el total de días de vacaciones disponibles para todo el historial
        dias_vacaciones = dias_disponibles

        context.update({
            'usuario': usuario,
            'dias_vacaciones': dias_vacaciones,
        })
        return context
    

class AprobarRechazarSolicitudView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Solicitud
    fields = ['estado']  # Solo permite cambiar el estado (Pendiente, Aprobada, Rechazada)
    template_name = 'aprobar_rechazar_solicitud.html'
    success_url = reverse_lazy('lista_solicitudes')

    def test_func(self):
        solicitud = self.get_object()

        # Evitar que el usuario apruebe su propia solicitud
        if solicitud.usuario == self.request.user:
            messages.error(self.request, 'No puedes aprobar o rechazar tu propia solicitud.')
            return False

        # Lógica de aprobación para diferentes roles
        if self.request.user.is_superuser or self.request.user.rol == 'GG':
            return True
        elif self.request.user.rol == 'JI':
            return solicitud.usuario.departamento.nombre in ['IT', 'ENERGIA', 'INDUSTRIA', 'TALLER']
        elif self.request.user.rol == 'JD':
            return solicitud.usuario in self.request.user.subordinados.all()
        return False

    def form_valid(self, form):
        solicitud = self.get_object()
        
        # Verificamos que el estado haya cambiado a 'Aprobada'
        if form.instance.estado == 'A':
            if solicitud.tipo == 'V':  # Vacaciones
                # Calcular el total de días disponibles incluyendo todos los años y ajustes
                dias_disponibles_totales = HistorialVacaciones.calcular_dias_disponibles_totales(solicitud.usuario)

                if solicitud.dias_solicitados > dias_disponibles_totales:
                    # Muestra una advertencia si el saldo será negativo
                    dias_faltantes = solicitud.dias_solicitados - dias_disponibles_totales
                    messages.warning(
                        self.request, 
                        f"Advertencia: Al aprobar esta solicitud, el saldo de días de vacaciones será negativo en {dias_faltantes} días."
                    )
                    return self.form_invalid(form)  # No permite la aprobación si los días son insuficientes

                # Resta los días solicitados de los registros históricos, empezando por los más antiguos
                dias_por_restar = solicitud.dias_solicitados
                historial_vacaciones = HistorialVacaciones.objects.filter(usuario=solicitud.usuario).order_by('año')
                
                for registro in historial_vacaciones:
                    dias_disponibles = registro.dias_disponibles()
                    if dias_por_restar <= dias_disponibles:
                        registro.dias_tomados += dias_por_restar
                        registro.save()
                        break
                    else:
                        registro.dias_tomados += dias_disponibles
                        dias_por_restar -= dias_disponibles
                        registro.save()

            elif solicitud.tipo == 'HC':  # Horas Compensatorias
                if solicitud.usuario.horas_compensatorias_disponibles >= solicitud.horas:
                    solicitud.usuario.horas_compensatorias_disponibles -= solicitud.horas
                    solicitud.usuario.save()  
                else:
                    messages.error(self.request, "No se puede aprobar. El usuario no tiene suficientes horas compensatorias.")
                    return self.form_invalid(form)

            elif solicitud.tipo == 'HE':  # Horas Extra
                if solicitud.usuario.horas_extra_acumuladas >= solicitud.horas:
                    solicitud.usuario.horas_extra_acumuladas -= solicitud.horas
                    solicitud.usuario.save()  # Actualizar el usuario en la base de datos
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
    success_url = reverse_lazy('dashboard')

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
        form.instance.usuario = self.request.user  # Asignar el usuario autenticado
        form.instance.estado = 'P'  # Estado pendiente por defecto

        # Validar según el rol del usuario
        rol_usuario = self.request.user.rol
        tipo_horas = form.cleaned_data.get('tipo')

        # Ingeniero (IN): Solo puede registrar horas compensatorias (HC)
        if rol_usuario == 'IN' and tipo_horas == 'HE':  # Horas Extra no permitidas para ingenieros
            form.add_error(None, "Los ingenieros no pueden registrar horas extra.")
            return self.form_invalid(form)

        # Jefes o Gerentes (GG, JI, JD): Solo pueden registrar horas compensatorias (HC)
        elif rol_usuario in ['GG', 'JI', 'JD'] and tipo_horas == 'HE':  # Horas Extra no permitidas para jefes o gerentes
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
        registro = self.get_object()
        return registro.usuario != self.request.user and self.request.user.rol in ['GG', 'JI', 'JD']


    def form_valid(self, form):
        registro = self.get_object()

        # Solo al aprobar/rechazar, asignar quién aprobó o rechazó las horas
        if form.instance.estado == 'A':  
            # Actualizar las horas extra o compensatorias del usuario
            if registro.tipo == 'HE':
                registro.usuario.horas_extra_acumuladas += registro.horas
                print(f"Horas extra después: {registro.usuario.horas_extra_acumuladas}")
            elif registro.tipo == 'HC':
                registro.usuario.horas_compensatorias_disponibles += registro.horas
                print(f"Horas compensatorias después: {registro.usuario.horas_compensatorias_disponibles}")
            registro.usuario.save()

        form.instance.aprobado_por = self.request.user  # Asignar quién aprobó las horas
        messages.success(self.request, 'El registro de horas ha sido procesado exitosamente.')
        return super().form_valid(form)


class ListaSolicitudesRegistrosPendientesView(ListView):
    template_name = 'lista_solicitudes.html'
    context_object_name = 'pendientes'

    def get_queryset(self):
        return []  # Retorna un queryset vacío para evitar la paginación automática de Django

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Filtrar y obtener registros de horas y solicitudes pendientes
        registros_queryset = RegistroHoras.objects.filter(estado='P')
        solicitudes_queryset = Solicitud.objects.filter(estado='P')

        # Filtrar por rol del usuario para que solo vea solicitudes y registros de sus subordinados
        if user.rol in ['GG', 'JI', 'JD']:
            registros_queryset = registros_queryset.filter(usuario__in=user.subordinados.all())
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=user.subordinados.all())
        else:
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()

        # Combinar ambos querysets en una lista
        pendientes = list(solicitudes_queryset) + list(registros_queryset)

        # Definir prioridad de estado y tipo de objeto
        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}  # Orden: Pendiente, Rechazado, Aprobado
        for item in pendientes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)  # Asigna el orden de prioridad del estado

        # Ordenar la lista combinada por `estado_orden` y luego por `id` en orden descendente
        pendientes = sorted(pendientes, key=attrgetter('estado_orden', 'fecha_inicio'))

        # Paginación manual
        paginator = Paginator(pendientes,8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Añadir al contexto
        context['pendientes'] = page_obj
        context['page_obj'] = page_obj  # Objeto de la página para usar en el template

        return context


class HistorialCombinadoView(ListView):
    template_name = 'historial_solicitudes.html'
    context_object_name = 'registros_y_solicitudes'
    
    def get_queryset(self):
        return []  # Retorna un queryset vacío para evitar la paginación automática de Django

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Obtener los valores de los filtros desde el formulario
        estado = self.request.GET.get('estado')
        tipo = self.request.GET.get('tipo')
        usuario_id = self.request.GET.get('usuario')

        # Filtrar los registros de horas de los subordinados del usuario
        registros_queryset = RegistroHoras.objects.filter(usuario__in=user.subordinados.all())
        # Filtrar las solicitudes de los subordinados del usuario
        solicitudes_queryset = Solicitud.objects.filter(usuario__in=user.subordinados.all())

        # Aplicar filtros
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

        # Añadir campo `tipo_objeto` y `estado_orden`
        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}
        for item in registros_y_solicitudes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)

        # Ordenar la lista combinada
        registros_y_solicitudes = sorted(registros_y_solicitudes, key=attrgetter('estado_orden', 'fecha_inicio'))

        # Paginación manual
        paginator = Paginator(registros_y_solicitudes, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Añadir al contexto
        context['registros_y_solicitudes'] = page_obj
        context['page_obj'] = page_obj
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)

        return context


class MiSolicitudYRegistroView(ListView):
    template_name = 'mis_solicitudes.html'
    context_object_name = 'solicitudes_y_registros'

    def get_queryset(self):
        return []  # Retorna un queryset vacío ya que la paginación se hará manualmente

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Obtener las solicitudes y registros de horas del usuario actual
        solicitudes_queryset = Solicitud.objects.filter(usuario=user)
        registros_queryset = RegistroHoras.objects.filter(usuario=user)

        # Aplicar filtro de estado a ambos querysets si está presente en la solicitud
        estado = self.request.GET.get('estado')
        if estado:
            solicitudes_queryset = solicitudes_queryset.filter(estado=estado)
            registros_queryset = registros_queryset.filter(estado=estado)

        # Combinar ambos querysets en una lista
        solicitudes_y_registros = list(solicitudes_queryset) + list(registros_queryset)

        # Añadir un campo `tipo_objeto` y `estado_orden` para diferenciar y ordenar
        estado_prioridad = {'P': 1, 'R': 2, 'A': 3}  # Prioridad: Pendiente, Rechazado, Aprobado
        for item in solicitudes_y_registros:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
            item.estado_orden = estado_prioridad.get(item.estado, 4)  # Asigna un valor de orden al estado

        # Ordenar la lista combinada primero por `estado_orden` y luego por cualquier otro criterio secundario
        solicitudes_y_registros = sorted(solicitudes_y_registros, key=attrgetter('estado_orden', 'fecha_inicio'))

        # Paginación manual de la lista combinada
        paginator = Paginator(solicitudes_y_registros,8)  # Paginación de 10 elementos por página
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Añadir la lista paginada al contexto
        context['solicitudes_y_registros'] = page_obj
        context['page_obj'] = page_obj  # Objeto de la página para usar en el template

        # Añadir el formulario de filtro al contexto
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=user)

        return context


def ajuste_vacaciones(request):
    # Verifica que el usuario tenga rol de jefe
    if request.user.rol not in ['GG', 'JI', 'JD']:
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('dashboard')  # Redirige a la página principal del dashboard

    usuarios = Usuario.objects.all()
    usuarios_vacaciones = []

    for usuario in usuarios:
        # Calcula el total de días asignados y tomados considerando todo el historial del usuario
        total_dias_asignados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_asignados'))['dias_asignados__sum'] or 0
        total_dias_tomados = HistorialVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_tomados'))['dias_tomados__sum'] or 0
        total_dias_ajustados = AjusteVacaciones.objects.filter(usuario=usuario).aggregate(Sum('dias_ajustados'))['dias_ajustados__sum'] or 0

        # Calcula el total de días disponibles incluyendo los ajustes
        dias_disponibles = total_dias_asignados - total_dias_tomados + total_dias_ajustados
        
        # Agrega un diccionario con los datos al listado de usuarios
        usuarios_vacaciones.append({
            'usuario': usuario,
            'dias_asignados': total_dias_asignados,
            'dias_tomados': total_dias_tomados,
            'dias_ajustados': total_dias_ajustados,
            'dias_disponibles': dias_disponibles,
        })

    # Manejo del formulario de ajuste de vacaciones
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        usuario = get_object_or_404(Usuario, id=usuario_id)
        form = AjusteVacacionesForm(request.POST)
        
        if form.is_valid():
            ajuste = form.save(commit=False)
            ajuste.usuario = usuario
            ajuste.año = date.today().year  # Registrar el año actual en el ajuste
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



def logout_view(request):
    logout(request)
    return redirect('login')