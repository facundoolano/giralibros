from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from books.models import LocationArea, OfferedBook, UserProfile, WantedBook


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that accepts email or username.
    Uses Django's localization for labels and error messages.
    """

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "tu@email.com o tu_usuario",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "••••••••",
            }
        )
    )


class RegistrationForm(UserCreationForm):
    """
    Registration form with username, email, and double password fields.
    Uses Django's UserCreationForm for password validation and matching.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "input",
                "placeholder": "tu@email.com",
            }
        ),
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "••••••••",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "••••••••",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "tu_usuario",
                }
            ),
        }

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este usuario ya está registrado")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email ya está registrado")
        return email


class ProfileForm(forms.Form):
    """
    Form for creating/editing user profile.
    Handles User.first_name, UserProfile fields, and UserLocation selections.
    """

    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Tu nombre",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "input",
                "placeholder": "tu@email.com",
            }
        )
    )
    alternate_contact = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "@usuario, teléfono, etc.",
            }
        ),
    )
    locations = forms.MultipleChoiceField(
        choices=LocationArea.choices,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    about = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "textarea",
                "rows": 4,
                "placeholder": "Lo que quieras que se vea en tu perfil público.",
            }
        ),
    )


class OfferedBookForm(forms.ModelForm):
    """
    Form for creating/editing an offered book.
    """

    class Meta:
        model = OfferedBook
        fields = ["title", "author", "notes"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "Título del libro",
                }
            ),
            "author": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "Autor",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "textarea",
                    "rows": 4,
                    "placeholder": "Observaciones (opcional)",
                }
            ),
        }


class WantedBookForm(forms.ModelForm):
    """
    Form for creating/editing a wanted book.
    """

    class Meta:
        model = WantedBook
        fields = ["title", "author"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "Título del libro",
                }
            ),
            "author": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "Autor",
                }
            ),
        }
