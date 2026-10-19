import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from .models import FacultyRequest, FacultyProfile, FacultyAvailability, FacultyLeave
from .services import scoped


class RequestForm(forms.ModelForm):
    class Meta:
        model = FacultyRequest
        fields = [
            "kind",
            "message",
            "starts_on",
            "ends_on",
            "day",
            "starts_at",
            "ends_at",
        ]


@login_required
@require_http_methods(["GET", "POST"])
def requests(request, pk=None):
    manager = request.user.is_institution_admin or request.user.role == "HOD"
    if not manager and request.user.role != "FACULTY":
        raise PermissionDenied
    qs = FacultyRequest.objects.select_related("faculty__user")
    if manager:
        qs = scoped(qs, request.user, "faculty__department_id")
    else:
        qs = qs.filter(faculty__user=request.user)
    if request.method == "GET":
        return JsonResponse(
            {
                "manager": manager,
                "rows": list(
                    qs.order_by("-created_at").values(
                        "id",
                        "faculty__user__username",
                        "kind",
                        "message",
                        "starts_on",
                        "ends_on",
                        "day",
                        "starts_at",
                        "ends_at",
                        "status",
                        "response",
                        "created_at",
                    )
                ),
            }
        )
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        from timetables.services import lock_scheduler, audit
        from timetables.models import Notification, Timetable
        from timetables.validators import validate_schedule

        with transaction.atomic():
            lock_scheduler()
            if pk:
                if not manager:
                    raise PermissionDenied
                obj = qs.select_for_update().filter(pk=pk).first()
                if not obj:
                    raise Http404
                if obj.status != "PENDING":
                    raise ValidationError("This request has already been reviewed.")
                status = data.get("status")
                if status not in ["APPROVED", "REJECTED"]:
                    raise ValidationError("Choose approved or rejected.")
                obj.status = status
                obj.response = str(data.get("response", ""))[:2000]
                obj.reviewed_by = request.user
                if status == "REJECTED" and not obj.response.strip():
                    raise ValidationError("A rejection reason is required.")
                if status == "APPROVED":
                    if obj.kind == "LEAVE":
                        FacultyLeave.objects.create(
                            faculty=obj.faculty,
                            starts_on=obj.starts_on,
                            ends_on=obj.ends_on,
                            reason=obj.message[:250],
                            approved=True,
                        )
                    elif obj.kind == "UNAVAILABLE":
                        FacultyAvailability.objects.create(
                            faculty=obj.faculty,
                            day=obj.day,
                            starts_at=obj.starts_at,
                            ends_at=obj.ends_at,
                            available=False,
                        )
                    for table in Timetable.objects.filter(status="PUBLISHED"):
                        issues = validate_schedule(
                            table,
                            list(
                                table.entries.select_related(
                                    "subject", "faculty__user", "room", "period"
                                )
                            ),
                            complete=True,
                        )
                        if any(i["severity"] == "error" for i in issues):
                            raise ValidationError(
                                "Revise or withdraw affected published schedules before approving this request."
                            )
                obj.save()
                Notification.objects.create(
                    user=obj.faculty.user,
                    message=f"Your {obj.kind.lower()} request was {obj.status.lower()}. {obj.response}"[
                        :500
                    ],
                )
                audit(request.user, obj, "review_request", {"status": status})
            else:
                faculty = FacultyProfile.objects.get(user=request.user)
                form = RequestForm(data)
                if not form.is_valid():
                    return JsonResponse({"errors": form.errors}, status=400)
                obj = form.save(commit=False)
                obj.faculty = faculty
                obj.save()
                audit(request.user, obj, "create_request")
            return JsonResponse({"id": obj.pk})
    except (ValueError, TypeError, ValidationError, ObjectDoesNotExist) as exc:
        return JsonResponse(
            {
                "errors": (
                    exc.messages
                    if isinstance(exc, ValidationError)
                    else "Invalid request data or missing faculty profile."
                )
            },
            status=400,
        )
