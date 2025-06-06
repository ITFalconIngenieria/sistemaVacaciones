from django.urls import path, re_path
from django.contrib.auth.views import LoginView
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Dashboard y autenticación
    path('', views.dashboard, name='dashboard'),
    path('login/', views.CustomLoginView.as_view(), name='login'),

    path('logout/', views.logout_view, name='logout'),

    # Usuarios
    path('crear-usuario/', views.CrearUsuarioView.as_view(), name='crear_usuario'),
    path('perfil-usuario/', views.PerfilUsuario, name='perfil_usuario'),
    path('cambiar-contrasena/', views.CambiarContrasenaView.as_view(), name='cambiar_contrasena'),

    # Solicitudes de vacaciones, horas extra y compensatorias
    path('crear-solicitud/', views.CrearSolicitudView.as_view(), name='crear_solicitud'),
    path('solicitudes/', views.ListaSolicitudesRegistrosPendientesView.as_view(), name='lista_solicitudes'),
    path('solicitud/<int:pk>/aprobar-rechazar/', views.AprobarRechazarSolicitudView.as_view(), name='aprobar_rechazar_solicitud'),
    path('historial-solicitudes/', views.HistorialCombinadoView.as_view(), name='historial_solicitudes'),
    path('mis-solicitudes/', views.MiSolicitudYRegistroView.as_view(), name='mis_solicitudes'),
    path('solicitud/editar/<int:pk>/', views.EditarMiSolicitudView.as_view(), name='editar_solicitud'),
    path('solicitud/eliminar/<int:pk>/', views.EliminarMiSolicitudView.as_view(), name='eliminar_solicitud'),
    path('reporte-solicitudes/', views.reporte_solicitudes, name='reporte_solicitudes'),
    path('reporte_solicitudes/pdf/', views.generar_reporte_solicitudes_pdf, name='generar_reporte_solicitudes_pdf'),
    path('solicitudes/jerarquia/', views.ListaSolicitudesRegistrosDosNivelesView.as_view(), name='solicitudes_jerarquicas'),

    # Registro de horas y aprobación
    path('registrar-horas/', views.RegistrarHorasView.as_view(), name='registrar_horas'),
    path('registro/editar/<int:pk>/', views.EditarMiRegistroHorasView.as_view(), name='editar_registro_horas'),
    path('registro/eliminar/<int:pk>/', views.EliminarMiRegistroHorasView.as_view(), name='eliminar_registro_horas'),
    path('aprobar-rechazar-horas/<int:pk>/', views.AprobarRechazarHorasView.as_view(), name='aprobar_rechazar_horas'),
    path('ajuste-vacaciones/', views.ajuste_vacaciones, name='ajuste_vacaciones'),
    path('historial-ajustes-vacaciones/', views.historial_ajustes_vacaciones, name='historial_ajustes_vacaciones'),
    path('reporte-horas-extra/', views.reporte_horas_extra_y_feriados_html, name='reporte_horas_extra_y_feriados'),
    path('generar-pdf/', views.reporte_horas_extra_y_feriados_pdf.as_view(), name='generar_pdf'),

    # Incapacidades
    path('incapacidades/crear/', views.CrearIncapacidadView.as_view(), name='crear_incapacidad'),
    path('incapacidades/', views.lista_incapacidades, name='lista_incapacidades'),
    path('mis_incapacidades/', views.MisIncapacidadesView.as_view(), name='mis_incapacidades'),
    path('incapacidad/editar/<int:pk>/', views.EditarIncapacidadView.as_view(), name='editar_incapacidad'),
    path('incapacidad/eliminar/<int:pk>/', views.EliminarIncapacidadView.as_view(), name='eliminar_incapacidad'),
    path('incapacidades/reporte/', views.GenerarReporteIncapacidadesView.as_view(), name='generar_reporte_incapacidades'),

    # Licencias
    path('crear-licencia/', views.CrearLicenciaView.as_view(), name='crear_licencia'),
    path('mis-licencias/', views.MisLicenciasView.as_view(), name='mis_licencias'),
    path('aprobar-licencia/<int:pk>/', views.AprobarRechazarLicenciaView.as_view(), name='aprobar_licencia'),
    path('editar-licencia/<int:pk>/', views.EditarLicenciaView.as_view(), name='editar_licencia'),
    path('eliminar-licencia/<int:pk>/', views.EliminarLicenciaView.as_view(), name='eliminar_licencia'),
    path('reporte-licencias/', views.reporte_licencias, name='reporte_licencias'),
    path('reporte-licencias-pdf/', views.generar_reporte_licencias_pdf, name='generar_reporte_licencias_pdf'),

    # Reportes y APIs adicionales
    path('convertir-vacaciones/', views.convertir_vacaciones_a_horas_view, name='convertir_vacaciones'),
    path('getferiados/', views.obtener_dias_feriados, name='obtener_dias_feriados'),
    path('colaboradores-info/', views.colaboradores_info, name='colaboradores_info'),
    path('solicitar-restablecimiento/', views.solicitar_restablecimiento, name='solicitar_restablecimiento'),
    path('verificar-codigo/', views.verificar_codigo, name='verificar_codigo'),
    path('reporte_horas_compensatorias/', views.reporte_horas_compensatorias, name='reporte_horas_compensatorias'),
    path('reporte_total_HC/', views.reporte_total_HC, name='reporte_total_HC'),
    path('api/pendientes/', views.obtener_cantidad_pendientes, name='obtener_cantidad_pendientes'),

    # Integración con Odoo
    path('registrar-horas-odoo/', views.registrar_horas_odoo, name='registrar_horas_odoo'),
    path('historial-horas-odoo/', views.historial_horas_odoo, name='historial_horas_odoo'),
    path('editar-registro-horas-odoo/<int:pk>/', views.editar_registro_horas_odoo, name='editar_registro_horas_odoo'),
    path('eliminar-registro-horas-odoo/<int:pk>/', views.eliminar_registro_horas_odoo, name='eliminar_registro_horas_odoo'),
    path('reporte-horas-pendientes-odoo/', views.reporte_horas_pendientes_odoo, name='reporte_horas_pendientes_odoo'),
    path('reporte_horas_ingresadas_por_usuario_odoo/', views.reporte_horas_ingresadas_por_usuario_odoo, name='reporte_horas_ingresadas_por_usuario_odoo'),

    path('reporte-descansos/', views.reporte_descansos, name='reporte_descansos'),
    path('reporte-descansos/pdf/', views.generar_reporte_descansos_pdf, name='generar_reporte_descansos_pdf'),

]

# Servir archivos estáticos en producción
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]