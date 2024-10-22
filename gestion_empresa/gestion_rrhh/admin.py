from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('rol', 'departamento', 'jefe')}),
    )

admin.site.register(Usuario, UsuarioAdmin)
