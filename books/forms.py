from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that accepts email or username.
    """
    username = forms.CharField(
        label='Email o usuario',
        widget=forms.TextInput(attrs={
            'class': 'input',
            'placeholder': 'tu@email.com o tu_usuario',
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': '••••••••',
        })
    )

    error_messages = {
        'invalid_login': 'Email/usuario o contraseña incorrectos',
        'inactive': 'Esta cuenta está inactiva.',
    }


class RegistrationForm(forms.ModelForm):
    """
    Registration form for new users.
    """
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': '••••••••',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'tu_usuario',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input',
                'placeholder': 'tu@email.com',
            }),
        }
        labels = {
            'username': 'Usuario',
            'email': 'Email',
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
