from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import User


class AccountForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Required for a new account; blank preserves the existing password.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "password",
        ]

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not self.instance.pk and not password:
            raise forms.ValidationError("A password is required for a new account.")
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data["password"]
        if password:
            user.set_password(password)
        elif user.pk:
            user.password = User.objects.get(pk=user.pk).password
        if commit:
            user.save()
        return user
