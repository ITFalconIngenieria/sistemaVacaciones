from django.contrib.auth.admin import UserAdmin
from .forms import UsuarioCreationForm, UsuarioChangeForm
from django.contrib import admin
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered
from .models import (
    Usuario, 
    FeriadoNacional, 
      HorasCompensatoriasDescanso,
    Departamento,
    Solicitud,
    RegistroHoras,
    HistorialVacaciones,
    AjusteVacaciones,
    Incapacidad,
    Licencia,
    ConversionVacacionesHoras,
    HorasCompensatoriasSieteDias,
    CodigoRestablecimiento,
    RegistroHorasOdoo
)


admin.site.register(Departamento)
admin.site.register(Solicitud)
admin.site.register(RegistroHoras)
admin.site.register(HistorialVacaciones)
admin.site.register(AjusteVacaciones)
admin.site.register(Incapacidad)
admin.site.register(Licencia)
admin.site.register(ConversionVacacionesHoras)
admin.site.register(HorasCompensatoriasSieteDias)
admin.site.register(CodigoRestablecimiento)
admin.site.register(RegistroHorasOdoo)



class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    model = Usuario

    fieldsets = UserAdmin.fieldsets + (
        ('Fechas importantes', {
            'fields': ('fecha_entrada', 'fecha_salida')
        }),
        ('Información Adicional', {
            'fields': ('rol', 'departamento', 'jefe', 'mostrar_en_dashboard')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email', 'rol', 'departamento', 'jefe', 'fecha_entrada', 'fecha_salida'),
        }),
    )

    # def save_model(self, request, obj, form, change):
    #     super().save_model(request, obj, form, change)


admin.site.register(Usuario, UsuarioAdmin)



@admin.register(FeriadoNacional)
class FeriadoNacionalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion') 
    search_fields = ('descripcion',) 
    list_filter = ('fecha',) 
    ordering = ('fecha',)
    date_hierarchy = 'fecha'



@admin.register(HorasCompensatoriasDescanso)
class HorasCompensatoriasDescansoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'registro_origen', 'inicio_descanso', 'fin_descanso', 'horas_compensadas', 'fecha_registro')
    list_filter = ('usuario', 'inicio_descanso')





app = apps.get_app_config('gestion_rrhh')

for model in app.get_models():
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        pass