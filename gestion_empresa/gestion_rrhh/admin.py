from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
     fieldsets = UserAdmin.fieldsets + (
        ('Fechas importantes', {
            'fields': ('fecha_entrada', 'fecha_salida')
        }),
        ('Información Adicional', {
            'fields': ('rol', 'departamento', 'jefe')
        }),
    )

admin.site.register(Usuario, UsuarioAdmin)
