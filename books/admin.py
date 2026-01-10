from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.db.models import Count, Exists, OuterRef

from .models import ExchangeRequest, OfferedBook, UserLocation, UserProfile, WantedBook


class CustomUserChangeForm(UserChangeForm):
    email = forms.EmailField(required=True)


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


class UserLocationInline(admin.TabularInline):
    model = UserLocation
    extra = 1
    verbose_name_plural = "Exchange Locations"


class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    inlines = [UserProfileInline, UserLocationInline]
    list_display = ["username", "email", "has_profile", "is_full_user", "offered_books_count", "date_joined", "last_login"]
    list_filter = ["is_staff", "is_superuser", "is_active", "date_joined"]
    ordering = ["-date_joined"]

    # Customize fieldsets to hide user permissions
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Ensure email appears in the add user form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with annotations for custom columns."""
        qs = super().get_queryset(request)
        qs = qs.annotate(
            has_profile_flag=Exists(
                UserProfile.objects.filter(user=OuterRef("pk"))
            ),
            offered_count=Count("offered")
        )
        return qs

    @admin.display(boolean=True, description="Has Profile")
    def has_profile(self, obj):
        return obj.has_profile_flag

    @admin.display(boolean=True, description="Is Full User")
    def is_full_user(self, obj):
        try:
            return obj.profile.is_full_user
        except UserProfile.DoesNotExist:
            return False

    @admin.display(description="Offered Books")
    def offered_books_count(self, obj):
        return obj.offered_count


# Unregister the default User admin and register our customized version
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Hide Groups from admin since we're not using them
admin.site.unregister(Group)


@admin.register(OfferedBook)
class OfferedBookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "user", "reserved", "created_at"]
    list_filter = ["reserved", "created_at"]
    search_fields = ["title", "author", "user__username"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"


@admin.register(WantedBook)
class WantedBookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["title", "author", "user__username"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ["from_user", "to_user", "book_title", "book_author", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["from_user__username", "to_user__username", "book_title", "book_author"]
    list_select_related = ["from_user", "to_user"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at"]
