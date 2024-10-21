from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
    # Configura cómo se mostrará el modelo en la administración
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('rol', 'departamento', 'jefe')}),
    )

admin.site.register(Usuario, UsuarioAdmin)
