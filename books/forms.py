from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that accepts email or username.
    Uses Django's localization for labels and error messages.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'input',
            'placeholder': 'tu@email.com o tu_usuario',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': '••••••••',
        })
    )


class RegistrationForm(forms.ModelForm):
    """
    Simple registration form with username, email, and single password field.
    Uses Django's localization for labels and error messages.
    """
    password = forms.CharField(
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

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuario ya está registrado')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email ya está registrado')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
