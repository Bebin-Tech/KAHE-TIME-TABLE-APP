from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .permissions import roles_required
from django.views.decorators.http import require_http_methods
from django.http import Http404
from django.db import transaction, IntegrityError
from django.db.models.deletion import ProtectedError
from .forms import AccountForm
import json


@login_required
def session(request):
    from academics.models import InstitutionSettings

    settings = InstitutionSettings.objects.first()
    user = request.user
    return JsonResponse(
        {
            "id": user.pk,
            "username": user.username,
            "role": user.role,
            "institution_admin": user.is_institution_admin,
            "timezone": settings.timezone if settings else "Asia/Kolkata",
        }
    )


@roles_required("ADMIN")
def users(request):
    from .models import User

    return JsonResponse(
        {"users": list(User.objects.values("id", "username", "role", "is_active"))}
    )


@roles_required("ADMIN")
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def account_records(request, pk=None):
    from .models import User
    from timetables.services import audit

    instance = User.objects.filter(pk=pk).first() if pk else None
    if pk and not instance:
        raise Http404
    if request.method == "GET":
        form = AccountForm(instance=instance)
        fields = [
            {
                "name": n,
                "label": str(f.label),
                "required": f.required,
                "kind": (
                    "password"
                    if n == "password"
                    else "checkbox" if n == "is_active" else "text"
                ),
                "choices": list(f.choices) if hasattr(f, "choices") else None,
                "initial": f.initial,
            }
            for n, f in form.fields.items()
        ]
        return JsonResponse(
            {
                "fields": fields,
                "rows": list(
                    User.objects.values(
                        "id",
                        "username",
                        "first_name",
                        "last_name",
                        "email",
                        "role",
                        "is_active",
                    )
                ),
                "writable": True,
            }
        )
    try:
        with transaction.atomic():
            if request.method == "DELETE":
                # Deactivation keeps account history and references intact.
                return JsonResponse(
                    {
                        "errors": "Deactivate accounts using Edit; account deletion is disabled."
                    },
                    status=400,
                )
            if request.method == "PUT" and not instance:
                raise Http404
            if request.method == "POST" and instance:
                raise Http404
            data = json.loads(request.body)
            if not isinstance(data, dict):
                raise ValueError
            form = AccountForm(data, instance=instance)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            if (
                instance
                and instance.pk == request.user.pk
                and (
                    not form.cleaned_data["is_active"]
                    or form.cleaned_data["role"] != "ADMIN"
                )
                and not instance.is_superuser
            ):
                return JsonResponse(
                    {
                        "errors": "You cannot deactivate or remove your own administrator role."
                    },
                    status=400,
                )
            user = form.save()
            audit(
                request.user,
                user,
                "account_update" if pk else "account_create",
                {"role": user.role, "active": user.is_active},
            )
            return JsonResponse({"id": user.pk}, status=200 if pk else 201)
    except (ValueError, IntegrityError, ProtectedError):
        return JsonResponse({"errors": "Invalid account data."}, status=400)
