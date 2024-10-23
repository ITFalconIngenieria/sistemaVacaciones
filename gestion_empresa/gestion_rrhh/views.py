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


class CrearSolicitudView(LoginRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = 'crear_solicitud.html'
    success_url = reverse_lazy('lista_solicitudes')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method in ('POST', 'PUT'):
            data = kwargs['data'].copy()
            data['usuario'] = self.request.user.id
            kwargs['data'] = data
        return kwargs

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P'

        try:
            # Validaciones específicas
            tipo_solicitud = form.cleaned_data.get('tipo')
            if tipo_solicitud == 'V':
                dias_vacaciones_disponibles = self.request.user.dias_vacaciones
                dias_solicitados = (form.cleaned_data.get('fecha_fin') - form.cleaned_data.get('fecha_inicio')).days + 1
                if dias_solicitados > dias_vacaciones_disponibles:
                    form.add_error(None, f"No tienes suficientes días de vacaciones disponibles (días disponibles: {dias_vacaciones_disponibles}).")
                    return self.form_invalid(form)

            elif tipo_solicitud == 'HC':
                if self.request.user.rol not in ['IN', 'GG', 'JI', 'JD']:
                    form.add_error(None, "No tienes permiso para solicitar horas compensatorias.")
                    return self.form_invalid(form)

                horas_compensatorias_disponibles = self.request.user.horas_compensatorias_disponibles
                horas_solicitadas = form.cleaned_data.get('horas')
                if horas_solicitadas > horas_compensatorias_disponibles:
                    form.add_error(None, f"No tienes suficientes horas compensatorias disponibles.")
                    return self.form_invalid(form)

            elif tipo_solicitud == 'HE':
                if self.request.user.rol != 'TE':
                    form.add_error(None, "Solo los técnicos pueden solicitar horas extra.")
                    return self.form_invalid(form)

            return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context



class ListaSolicitudesView(LoginRequiredMixin, ListView):
    model = Solicitud
    template_name = 'lista_solicitudes.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        if self.request.user.is_superuser  or self.request.user.rol in ['GG', 'JI', 'JD']:
            return Solicitud.objects.filter(estado='P')
        return Solicitud.objects.filter(usuario=self.request.user)




class AprobarRechazarSolicitudView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Solicitud
    fields = ['estado']  # Solo permite cambiar el estado (Pendiente, Aprobado, Rechazado)
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

        # Solo al aprobar/rechazar, asignar quién aprobó o rechazó la solicitud
        if form.instance.estado in ['A', 'R']:
            form.instance.aprobado_por = self.request.user

            # Lógica de manejo al aprobar la solicitud (Restar)
            if form.instance.estado == 'A':
                if solicitud.tipo == 'V':  # Vacaciones
                    dias_solicitados = (solicitud.fecha_fin - solicitud.fecha_inicio).days + 1
                    solicitud.usuario.dias_vacaciones -= dias_solicitados
                    solicitud.usuario.save()

                elif solicitud.tipo == 'HC':  # Horas Compensatorias
                    solicitud.usuario.horas_compensatorias_disponibles -= solicitud.horas
                    solicitud.usuario.save()

                elif solicitud.tipo == 'HE':  # Horas Extra
                    solicitud.usuario.horas_extra_acumuladas -= solicitud.horas
                    solicitud.usuario.save()

            messages.success(self.request, 'La solicitud ha sido procesada exitosamente.')
        return super().form_valid(form)





class HistorialSolicitudesView(ListView):
    model = Solicitud
    template_name = 'historial_solicitudes.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        user = self.request.user
        queryset = Solicitud.objects.all()

        # Obtener los valores de los filtros desde el formulario
        estado = self.request.GET.get('estado')
        tipo = self.request.GET.get('tipo')
        usuario_id = self.request.GET.get('usuario')

        # Si es jefe, filtrar sus propias solicitudes y las de sus subordinados
        if user.rol in ['GG', 'JI', 'JD']:
            queryset = queryset.filter(usuario__in=[user] + list(user.subordinados.all()))
        else:
            # Si no es jefe, solo ver sus propias solicitudes
            queryset = queryset.filter(usuario=user)

        # Filtrar por estado si se seleccionó
        if estado:
            queryset = queryset.filter(estado=estado)

        # Filtrar por tipo de solicitud si se seleccionó
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        # Filtrar por usuario si es jefe y se seleccionó un usuario
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar la lista de subordinados al contexto si el usuario es jefe
        if self.request.user.rol in ['GG', 'JI', 'JD']:
            context['subordinados'] = Usuario.objects.filter(jefe=self.request.user)
        return context


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
        tipo_horas = form.cleaned_data.get('tipo_horas')

        # Ingeniero (IN): Solo puede registrar horas compensatorias (HC)
        if rol_usuario == 'IN' and tipo_horas == 'HE':  # Horas Extra no permitidas para ingenieros
            form.add_error(None, "Los ingenieros no pueden registrar horas extra.")
            return self.form_invalid(form)

        # Técnico (TE): Solo puede registrar horas extra (HE)
        elif rol_usuario == 'TE' and tipo_horas == 'HC':  # Horas Compensatorias no permitidas para técnicos
            form.add_error(None, "Los técnicos solo pueden registrar horas extra.")
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

        # No permitir que el jefe apruebe su propia solicitud
        if registro.usuario == self.request.user:
            messages.error(self.request, 'No puedes aprobar o rechazar tus propias horas.')
            return False

        # Permitir que jefes aprueben las solicitudes de sus subordinados
        if self.request.user.rol in ['GG', 'JI', 'JD']:
            return True
        return False

    def form_valid(self, form):
        registro = form.save(commit=False)

        # Solo al aprobar/rechazar, asignar quién aprobó o rechazó las horas
        if registro.estado in ['A', 'R']:
            registro.aprobado_por = self.request.user
            if registro.estado == 'A':  # Si la solicitud es aprobada
                # Actualizar las horas extra o compensatorias del usuario
                if registro.tipo_horas == 'HE':
                    registro.usuario.horas_extra_acumuladas += registro.horas
                elif registro.tipo_horas == 'HC':
                    registro.usuario.horas_compensatorias_disponibles += registro.horas
                registro.usuario.save()

        messages.success(self.request, 'El registro de horas ha sido procesado exitosamente.')
        return super().form_valid(form)



class ListaHorasPendientesView(ListView):
    model = RegistroHoras
    template_name = 'lista_horas_pendientes.html'
    context_object_name = 'registros_horas'

    def get_queryset(self):
        user = self.request.user
        queryset = RegistroHoras.objects.filter(estado='P')  # Filtrar solo las horas pendientes

        # Si el usuario es un jefe, ver sus solicitudes y las de sus subordinados
        if user.rol in ['GG', 'JI', 'JD']:
            queryset = queryset.filter(usuario__in=[user] + list(user.subordinados.all()))
        
        # Si no es jefe, no debería ver ninguna solicitud
        else:
            queryset = RegistroHoras.objects.none()

        return queryset


class ListaRegistroHorasView(ListView):
    model = RegistroHoras
    template_name = 'historial_registro_horas.html'
    context_object_name = 'registros_horas'

    def get_queryset(self):
        user = self.request.user
        queryset = RegistroHoras.objects.all()

        # Obtener los datos del formulario de filtro
        estado = self.request.GET.get('estado')
        usuario_id = self.request.GET.get('usuario')

        # Si es jefe, ver sus registros y los de sus subordinados
        if user.rol in ['GG', 'JI', 'JD']:
            queryset = queryset.filter(usuario__in=[user] + list(user.subordinados.all()))
        else:
            # Si no es jefe, solo ver sus propios registros
            queryset = queryset.filter(usuario=user)

        # Filtro por estado
        if estado:
            queryset = queryset.filter(estado=estado)

        # Filtro por usuario (solo si es jefe)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir el formulario de filtro al contexto, pasando el usuario autenticado
        context['filter_form'] = RegistroHorasFilterForm(self.request.GET or None, user=self.request.user)

        return context


def logout_view(request):
    logout(request)
    return redirect('login')