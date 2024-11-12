from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect,  redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from .models import Usuario, Solicitud
from .forms import UsuarioCreationForm, SolicitudForm, RegistrarHorasForm,RegistroHorasFilterForm
from django.contrib import messages
from django.contrib.auth import logout
from .models import RegistroHoras
from django.core.exceptions import ValidationError
from operator import attrgetter
from django.core.paginator import Paginator
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

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

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P'
        tipo_solicitud = form.cleaned_data.get('tipo')
        print("tipo solicitud" , tipo_solicitud)
        fecha_inicio = form.cleaned_data.get('fecha_inicio')
        fecha_fin = form.cleaned_data.get('fecha_fin')
        if tipo_solicitud == 'V':  # Vacaciones
            dias_solicitados = (fecha_fin.date() - fecha_inicio.date()).days + 1
            form.instance.dias_solicitados = dias_solicitados
            # Verifica si el usuario tiene suficientes días de vacaciones
            if dias_solicitados > self.request.user.dias_vacaciones:
                # Mostrar una advertencia en lugar de bloquear la solicitud
                messages.warning(
                    self.request, 
                    f"Advertencia: estás solicitando {dias_solicitados} días, pero solo tienes {self.request.user.dias_vacaciones} días disponibles. Esto resultará en un saldo negativo."
                )

        if tipo_solicitud == 'HC':
            print("si entra")
            diferencia = fecha_fin - fecha_inicio
            horas_solicitadas = diferencia.total_seconds() / 3600
            if horas_solicitadas > self.request.user.horas_compensatorias_disponibles:
                form.add_error(None, f"No tienes suficientes horas compensatorias disponibles (horas disponibles: {self.request.user.horas_compensatorias_disponibles}).")
                return self.form_invalid(form)
            else:
                form.instance.horas = horas_solicitadas

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context

class AprobarRechazarSolicitudView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Solicitud
    fields = ['estado']  # Solo permite cambiar el estado (Pendiente, Aprobado, Rechazado)
    template_name = 'aprobar_rechazar_solicitud.html'
    success_url = reverse_lazy('mis_solicitudes')

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
        solicitud.usuario.recalcular_vacaciones = False
        # Verificamos que el estado haya cambiado a 'Aprobada'
        if form.instance.estado == 'A':
            if solicitud.tipo == 'V':  # Vacaciones
                dias_faltantes = solicitud.usuario.dias_vacaciones - solicitud.dias_solicitados
                if dias_faltantes < 0:
                    # Muestra una advertencia si el saldo será negativo
                    messages.warning(self.request, f"Advertencia: Al aprobar esta solicitud, el saldo de días de vacaciones será negativo ({dias_faltantes}).")
                solicitud.usuario.dias_vacaciones -= solicitud.dias_solicitados
                solicitud.usuario.save()
            elif solicitud.tipo == 'HC':  
                if solicitud.usuario.horas_compensatorias_disponibles >= solicitud.horas:
                    solicitud.usuario.horas_compensatorias_disponibles -= solicitud.horas
                    solicitud.usuario.save()  
                else:
                    messages.error(self.request, f"No se puede aprobar. El usuario no tiene suficientes horas compensatorias.")
                    return self.form_invalid(form)

            elif solicitud.tipo == 'HE':  # Horas Extra
                if solicitud.usuario.horas_extra_acumuladas >= solicitud.horas:
                    solicitud.usuario.horas_extra_acumuladas -= solicitud.horas
                    solicitud.usuario.save()  # Actualizar el usuario en la base de datos
                    print(f"Horas extra después: {solicitud.usuario.horas_extra_acumuladas}")
                else:
                    messages.error(self.request, f"No se puede aprobar. El usuario no tiene suficientes horas extra.")
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

        messages.success(self.request, 'Registro de horas creado y pendiente de aprobación.')
        return super().form_valid(form)

class AprobarRechazarHorasView(UserPassesTestMixin, UpdateView):
    model = RegistroHoras
    fields = ['estado']
    template_name = 'aprobar_rechazar_horas.html'
    success_url = reverse_lazy('lista_horas_pendientes')

    def test_func(self):
        registro = self.get_object()
        registro = self.get_object()
        return registro.usuario != self.request.user and self.request.user.rol in ['GG', 'JI', 'JD']


    def form_valid(self, form):
        registro = self.get_object()

        # Solo al aprobar/rechazar, asignar quién aprobó o rechazó las horas
        if form.instance.estado == 'A':  # Si la solicitud es aprobada
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
        
        # Filtrar registros de horas pendientes
        registros_queryset = RegistroHoras.objects.filter(estado='P')
        # Filtrar solicitudes pendientes
        solicitudes_queryset = Solicitud.objects.filter(estado='P')
        
        # Filtrar por rol del usuario
        if user.rol in ['GG', 'JI', 'JD']:  # Si el usuario es jefe
            registros_queryset = registros_queryset.filter(usuario__in=user.subordinados.all())
            solicitudes_queryset = solicitudes_queryset.filter(usuario__in=user.subordinados.all())
        else:  # Si no es jefe, mostrar listas vacías
            registros_queryset = RegistroHoras.objects.none()
            solicitudes_queryset = Solicitud.objects.none()
        
        # Combinar los querysets
        pendientes = list(registros_queryset) + list(solicitudes_queryset)
        
        # Añadir `tipo_objeto` para distinguir
        for item in pendientes:
            item.tipo_objeto = 'solicitud' if isinstance(item, Solicitud) else 'registro'
        
        # Paginación manual
        paginator = Paginator(pendientes, 10)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Añadir al contexto
        context['pendientes'] = page_obj
        context['page_obj'] = page_obj

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
        paginator = Paginator(registros_y_solicitudes, 10)
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

def logout_view(request):
    logout(request)
    return redirect('login')