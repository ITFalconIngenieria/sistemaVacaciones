from django.urls import path
from django.contrib.auth.views import LoginView
from . import views
from django.conf.urls.static import static
from django.conf import settings
urlpatterns = [
    # Dashboard y autenticación
    path('', views.dashboard, name='dashboard'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Usuarios
    path('crear-usuario/', views.CrearUsuarioView.as_view(), name='crear_usuario'),

    path('perfil-usuario/', views.PerfilUsuario, name='perfil_usuario'),
    path('cambiar-contrasena/', views.CambiarContrasenaView.as_view(), name='cambiar_contrasena'),

    #Solicitudes de vacaciones/horas extra/compensatorias
    path('crear-solicitud/', views.CrearSolicitudView.as_view(), name='crear_solicitud'),
    path('solicitudes/', views.ListaSolicitudesRegistrosPendientesView.as_view(), name='lista_solicitudes'),  # Ruta única para la lista de solicitudes
    path('solicitud/<int:pk>/aprobar-rechazar/', views.AprobarRechazarSolicitudView.as_view(), name='aprobar_rechazar_solicitud'),
    path('historial-solicitudes/', views.HistorialCombinadoView.as_view(), name='historial_solicitudes'),
    path('mis-solicitudes/', views.MiSolicitudYRegistroView.as_view(), name='mis_solicitudes'),

    # Registro de horas y aprobación
    path('registrar-horas/', views.RegistrarHorasView.as_view(), name='registrar_horas'),
    path('aprobar-rechazar-horas/<int:pk>/', views.AprobarRechazarHorasView.as_view(), name='aprobar_rechazar_horas'),

    path('ajuste-vacaciones/', views.ajuste_vacaciones, name='ajuste_vacaciones'),


    path('reporte-horas-extra/',views.reporte_horas_extra, name='reporte_horas_extra'),
    path('cerrar-quincena/', views.cerrar_quincena, name='cerrar_quincena'),

    path('generar-pdf/', views.GenPdf.as_view(), name='generar_pdf'),




    path('incapacidades/crear/', views.CrearIncapacidadView.as_view(), name='crear_incapacidad'),
    # path('incapacidades/', views.ListaIncapacidadesView.as_view(), name='lista_incapacidades'),
    path('incapacidades/', views.lista_incapacidades, name='lista_incapacidades'),



     path('solicitud/editar/<int:pk>/', views.EditarSolicitudView.as_view(), name='editar_solicitud'),
    path('registro/editar/<int:pk>/', views.EditarRegistroHorasView.as_view(), name='editar_registro_horas'),
    path('solicitud/eliminar/<int:pk>/', views.EliminarSolicitudView.as_view(), name='eliminar_solicitud'),
    path('registro/eliminar/<int:pk>/', views.EliminarRegistroHorasView.as_view(), name='eliminar_registro_horas'),
    
    


]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
