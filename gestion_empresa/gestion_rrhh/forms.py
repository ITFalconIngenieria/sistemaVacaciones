
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Solicitud, RegistroHoras, Usuario, AjusteVacaciones, FeriadoNacional, Incapacidad
from .validators import validate_username
from django.utils import timezone
from django.core.exceptions import ValidationError
from django import forms
from datetime import date
class UsuarioCreationForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'rol', 'departamento', 'jefe', 'fecha_entrada', 'fecha_salida']

        # widgets = {
        #     'fecha_entrada': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        #     'fecha_salida': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        # }



class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = UserChangeForm.Meta.fields

class SolicitudForm(forms.ModelForm):
    confirmacion_requisitos = forms.BooleanField(
        required=True,
        label="Confirmo que he leído y acepto los requisitos (tener registro de horas al día en Odoo y atender llamadas, mensajes y correos).",
        error_messages={'required': 'Debe confirmar que está de acuerdo con los requisitos antes de continuar.'}
    )

    class Meta:
        model = Solicitud
        fields = ['numero_solicitud', 'tipo', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'numero_solicitud': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'fecha_inicio': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
            'fecha_fin': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
        }
        exclude = ['estado', 'aprobado_por']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields['tipo'].widget.attrs['readonly'] = True  
            self.fields['tipo'].widget.attrs['style'] = 'pointer-events: none;'

            if self.instance.fecha_inicio:
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%dT%H:%M')
            if self.instance.fecha_fin:
                self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        confirmacion_requisitos = cleaned_data.get('confirmacion_requisitos')

        if not fecha_inicio or not fecha_fin:
            raise forms.ValidationError("Las fechas de inicio y fin son obligatorias.")

        if fecha_inicio > fecha_fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")

        fecha_actual = timezone.now()
        if fecha_inicio.date() < fecha_actual.date():
            raise forms.ValidationError("La fecha de inicio no puede ser anterior a la fecha actual.")

        if not confirmacion_requisitos:
            raise forms.ValidationError("Debe confirmar que está de acuerdo con los requisitos antes de enviar la solicitud.")

        return cleaned_data




class RegistrarHorasForm(forms.ModelForm):
    class Meta:
        model = RegistroHoras
        fields = ['numero_registro', 'tipo', 'fecha_inicio', 'fecha_fin','numero_proyecto', 'descripcion']
        widgets = {
             'numero_registro': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'  # Campo solo lectura
            }),
            'fecha_inicio': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
            'fecha_fin': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),'numero_proyecto': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Numero de Proyecto',
                    'min': '0' 
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['tipo'].widget.attrs['readonly'] = True
            self.fields['tipo'].widget.attrs['style'] = 'pointer-events: none;'
            
            if self.instance.fecha_inicio:
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%dT%H:%M')
            if self.instance.fecha_fin:
                self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        numero_proyecto = cleaned_data.get('numero_proyecto')
        descripcion = cleaned_data.get('descripcion')
        fecha_actual = timezone.now()
        if (numero_proyecto is None or numero_proyecto == 0) and not descripcion:
            raise forms.ValidationError(
                "Debe llenar la descripción porque el número de proyecto está vacío o es 0."
            )

        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise forms.ValidationError("La fecha y hora de fin deben ser posteriores a la fecha y hora de inicio.")
        
        if fecha_inicio and fecha_inicio > fecha_actual:
            raise forms.ValidationError("Imposible registrar horas para el futuro. Favor valide la fecha y hora de inicio.")
    
        if fecha_fin and fecha_fin >= fecha_actual:
            raise forms.ValidationError("Imposible registrar horas para el futuro. Favor valide la fecha y hora de fin.")

        return cleaned_data
    
class RegistroHorasFilterForm(forms.Form):
    ESTADOS = (
        ('P', 'Pendiente'),
        ('A', 'Aprobada'),
        ('R', 'Rechazada'),
    )
    estado = forms.ChoiceField(choices=[('', 'Todos')] + list(ESTADOS), required=False, label="Estado")
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.none(), required=False, label="Usuario")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and self.user.rol in ['GG', 'JI', 'JD']:
            self.fields['usuario'].queryset = Usuario.objects.filter(jefe=self.user) | Usuario.objects.filter(id=self.user.id)
        else:
            del self.fields['usuario']


class AjusteVacacionesForm(forms.ModelForm):
    class Meta:
        model = AjusteVacaciones
        fields = ['descripcion', 'dias_ajustados']
        labels = {
            'descripcion': 'Descripción del Ajuste',
            'dias_ajustados': 'Días de Vacaciones Ajustados',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={
                'rows': 3,  
                'style': 'width: 100%; resize: none;',
                'placeholder': 'Motivo del ajuste', 
            }),
            'dias_ajustados': forms.NumberInput(attrs={
                'style': 'width: 50%;', 
            })
        }


class IncapacidadForm(forms.ModelForm):
    class Meta:
        model = Incapacidad
        fields = ['fecha_inicio', 'fecha_fin', 'archivo_adjunto', 'descripcion']
        widgets = {

            'fecha_inicio': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
            'fecha_fin': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'archivo_adjunto': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.fecha_inicio:
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%d')
            if self.instance.fecha_fin:
                self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%d')

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        hoy = date.today()

        if not fecha_inicio or not fecha_fin:
            raise forms.ValidationError("Ambas fechas son obligatorias.")

        if fecha_inicio < hoy:
            raise forms.ValidationError("La fecha de inicio no puede ser menor a la fecha actual.")

        if fecha_fin < fecha_inicio:
            raise forms.ValidationError("La fecha de fin no puede ser menor a la fecha de inicio.")

        if fecha_fin < hoy:
            raise forms.ValidationError("La fecha de fin no puede ser menor a la fecha actual.")

        return cleaned_data
    



class FeriadoNacionalForm(forms.ModelForm):
    class Meta:
        model = FeriadoNacional
        fields = ['fecha', 'descripcion']
        widgets = {
           'fecha': forms.TextInput(attrs={
                'class': 'form-control flatpickr-datetime',
                'required': 'required'
            }),
        }
        labels = {
            'fecha': 'Fecha del Feriado',
            'descripcion': 'Descripción',
        }
