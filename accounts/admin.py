from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CTMSUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("College access", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("College access", {"fields": ("role", "email")}),
    )
    list_display = ("username", "email", "role", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)
