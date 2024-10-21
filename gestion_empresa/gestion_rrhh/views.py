from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from .models import Usuario, Solicitud
from .forms import UsuarioCreationForm, SolicitudForm
from django.contrib import messages
from django.contrib.auth import logout

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

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = 'P' 
        return super().form_valid(form)

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
        # Solo al aprobar/rechazar, asignar quién aprobó o rechazó la solicitud
        if form.instance.estado in ['A', 'R']:
            form.instance.aprobado_por = self.request.user
        messages.success(self.request, 'La solicitud ha sido procesada exitosamente.')
        return super().form_valid(form)

# class HistorialSolicitudesView(LoginRequiredMixin, ListView):
#     model = Solicitud
#     template_name = 'historial_solicitudes.html'  # Nueva plantilla para el historial
#     context_object_name = 'solicitudes'
    
#     def get_queryset(self):
#         # Si el usuario es un jefe (o superuser), puede ver todas las solicitudes
#         if self.request.user.is_superuser or self.request.user.rol in ['GG', 'JI', 'JD']:
#             return Solicitud.objects.all()
#         # De lo contrario, muestra solo las solicitudes del usuario autenticado
#         return Solicitud.objects.filter(usuario=self.request.user).order_by('-fecha_inicio')


class HistorialSolicitudesView(LoginRequiredMixin, ListView):
    model = Solicitud
    template_name = 'historial_solicitudes.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        estado = self.request.GET.get('estado')  # Obtén el filtro del parámetro 'estado'
        
        # Jefes pueden ver todas las solicitudes
        if self.request.user.is_superuser or self.request.user.rol in ['GG', 'JI', 'JD']:
            queryset = Solicitud.objects.all()
        else:
            queryset = Solicitud.objects.filter(usuario=self.request.user)

        if estado:
            queryset = queryset.filter(estado=estado)  # Filtra por estado si se proporciona
        return queryset.order_by('-fecha_inicio')


def logout_view(request):
    logout(request)
    return redirect('login')