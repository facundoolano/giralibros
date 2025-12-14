from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User

from books.models import LocationArea, OfferedBook, WantedBook


class BulmaFormMixin:
    """
    Mixin that automatically applies Bulma CSS classes to form widgets.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget_class = field.widget.__class__.__name__

            # Determine the appropriate Bulma class
            if widget_class in [
                "TextInput",
                "EmailInput",
                "PasswordInput",
                "NumberInput",
                "URLInput",
            ]:
                css_class = "input"
            elif widget_class == "Textarea":
                css_class = "textarea"
            elif widget_class in ["Select", "SelectMultiple"]:
                css_class = "select"
            else:
                continue

            # Add the class to existing attrs
            existing_class = field.widget.attrs.get("class", "")
            if css_class not in existing_class:
                field.widget.attrs["class"] = f"{existing_class} {css_class}".strip()


class EmailOrUsernameAuthenticationForm(BulmaFormMixin, AuthenticationForm):
    """
    Custom authentication form that accepts email or username.
    Uses Django's localization for labels and error messages.
    """

    username = forms.CharField(label="Usuario o email")


class RegistrationForm(BulmaFormMixin, UserCreationForm):
    """
    Registration form with username, email, and double password fields.
    Uses Django's UserCreationForm for password validation and matching.
    """

    email = forms.EmailField(required=True)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput())
    password2 = forms.CharField(
        label="Confirmar contraseña", widget=forms.PasswordInput()
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

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


class PasswordResetRequestForm(BulmaFormMixin, PasswordResetForm):
    """
    PasswordResetForm with Bulma CSS styling.
    """

    pass


class CustomSetPasswordForm(BulmaFormMixin, SetPasswordForm):
    """
    SetPasswordForm with Bulma CSS styling.
    """

    pass


class ProfileForm(BulmaFormMixin, forms.Form):
    """
    Form for creating/editing user profile.
    Handles User.first_name, UserProfile fields, and UserLocation selections.
    """

    first_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    alternate_contact = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "@usuario, teléfono, etc."}),
    )
    locations = forms.MultipleChoiceField(
        choices=LocationArea.choices,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    about = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Lo que quieras que se vea en tu perfil público.",
                "maxlength": 200,
            }
        ),
    )


class OfferedBookForm(BulmaFormMixin, forms.ModelForm):
    """
    Form for creating/editing an offered book.
    """

    temp_cover_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = OfferedBook
        fields = ["title", "author", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Título del libro"}),
            "author": forms.TextInput(attrs={"placeholder": "Autor"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Observaciones (opcional)",
                    "maxlength": 300,
                }
            ),
        }


class WantedBookForm(BulmaFormMixin, forms.ModelForm):
    """
    Form for creating/editing a wanted book.
    """

    class Meta:
        model = WantedBook
        fields = ["author", "title"]
