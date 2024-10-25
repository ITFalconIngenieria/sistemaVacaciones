from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario, Solicitud
from django import forms
from .models import RegistroHoras, Usuario
from .validators import validate_username

class UsuarioCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        validators=[validate_username],  # Aplicar el validador de solo letras
        help_text="Solo letras, sin números ni caracteres especiales."
    )
    
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'rol', 'departamento', 'jefe', 'fecha_entrada', 'fecha_salida', 'password1', 'password2']
        widgets = {
            'fecha_entrada': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_salida': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = UserChangeForm.Meta.fields

# class SolicitudForm(forms.ModelForm):
#     class Meta:
#         model = Solicitud
#         fields = ['tipo', 'fecha_inicio', 'fecha_fin', 'horas']
#         widgets = {
#             'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
#             'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
#         }
#         exclude = ['estado', 'aprobado_por']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['horas'].required = False
    


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ['tipo', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control',
                    'required': 'required'
                }
            ),
            'fecha_fin': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control',
                    'required': 'required'
                }
            )
        }
        exclude = ['estado', 'aprobado_por']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Verificar si la instancia existe y si tiene un tipo
        if 'instance' in kwargs and kwargs['instance'] is not None:
            if kwargs['instance'].tipo == 'V':
                self.fields['fecha_fin'].required = True  # Ejemplo, podrías ajustar otra lógica aquí.



class RegistrarHorasForm(forms.ModelForm):
    class Meta:
        model = RegistroHoras
        fields = ['tipo_horas', 'fecha_inicio', 'fecha_fin', 'descripcion']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control',
                    'required': 'required'
                }
            ),
            'fecha_fin': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control',
                    'required': 'required'
                }
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'form-control',
                    'placeholder': 'Describa brevemente el trabajo realizado'
                }
            )
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')

        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise forms.ValidationError("La fecha y hora de fin deben ser posteriores a la fecha y hora de inicio.")

        return cleaned_data
    
class RegistroHorasFilterForm(forms.Form):
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )

    # Campo para filtrar por estado
    estado = forms.ChoiceField(choices=[('', 'Todos')] + list(ESTADOS), required=False, label="Estado")
    
    # Campo para filtrar por usuario (solo disponible para jefes)
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.none(), required=False, label="Usuario")

    def __init__(self, *args, **kwargs):
        # Obtener el usuario autenticado del formulario
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Si el usuario es jefe, mostrar sus subordinados más él mismo
        if self.user and self.user.rol in ['GG', 'JI', 'JD']:
            self.fields['usuario'].queryset = Usuario.objects.filter(jefe=self.user) | Usuario.objects.filter(id=self.user.id)
        else:
            # Si no es jefe, ocultar el campo de usuario (asignar su propio registro)
            del self.fields['usuario']