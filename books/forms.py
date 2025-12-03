from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
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


class RegistrationForm(forms.ModelForm):
    """
    Simple registration form with username, email, and single password field.
    Uses Django's localization for labels and error messages.
    """

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "••••••••",
            }
        )
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "tu_usuario",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "input",
                    "placeholder": "tu@email.com",
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

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            # FIXME this seems like it's manually doing validations that should be already
            # provided by the django auth forms

            # Create a temporary user with submitted data for validation
            # This allows validators to check password similarity with username/email
            user = User(
                username=self.cleaned_data.get("username"),
                email=self.cleaned_data.get("email"),
            )
            # Validate password using Django's configured validators
            # This will use AUTH_PASSWORD_VALIDATORS from settings
            # (which is empty in dev but enforced in production/test)
            password_validation.validate_password(password, user)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


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
