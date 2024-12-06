from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, FeriadoNacional


class UsuarioAdmin(UserAdmin):
     fieldsets = UserAdmin.fieldsets + (
        ('Fechas importantes', {
            'fields': ('fecha_entrada', 'fecha_salida')
        }),
        ('Información Adicional', {
            'fields': ('rol', 'departamento', 'jefe','mostrar_en_dashboard')
        }),
    )

admin.site.register(Usuario, UsuarioAdmin)



@admin.register(FeriadoNacional)
class FeriadoNacionalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion') 
    search_fields = ('descripcion',) 
    list_filter = ('fecha',) 
    ordering = ('fecha',)
    date_hierarchy = 'fecha'         