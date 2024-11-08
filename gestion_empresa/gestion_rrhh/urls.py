from django.urls import path
from django.contrib.auth.views import LoginView
from . import views

urlpatterns = [
    # Dashboard y autenticación
    path('', views.dashboard, name='dashboard'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Usuarios
    path('crear-usuario/', views.CrearUsuarioView.as_view(), name='crear_usuario'),

    # Solicitudes de vacaciones/horas extra/compensatorias
    path('crear-solicitud/', views.CrearSolicitudView.as_view(), name='crear_solicitud'),
    path('solicitudes/', views.ListaSolicitudesView.as_view(), name='lista_solicitudes'),  # Ruta única para la lista de solicitudes
    path('solicitud/<int:pk>/aprobar-rechazar/', views.AprobarRechazarSolicitudView.as_view(), name='aprobar_rechazar_solicitud'),
    path('historial-solicitudes/', views.HistorialSolicitudesView.as_view(), name='historial_solicitudes'),
    path('mis-solicitudes/', views.HistorialMisSolicitudesView.as_view(), name='mis_solicitudes'),

    # Registro de horas y aprobación
    path('registrar-horas/', views.RegistrarHorasView.as_view(), name='registrar_horas'),
    path('lista-horas-pendientes/', views.ListaHorasPendientesView.as_view(), name='lista_horas_pendientes'),
    path('aprobar-rechazar-horas/<int:pk>/', views.AprobarRechazarHorasView.as_view(), name='aprobar_rechazar_horas'),

    path('mis-registros-horas/', views.ListaRegistroHorasView.as_view(), name='mis_registros_horas'),
]
