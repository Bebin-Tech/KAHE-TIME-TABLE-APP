import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from . import models
from .services import scoped

# A single registry keeps form validation and query scoping consistent across CRUD.
REGISTRY = {
    "departments": (models.Department, "pk", False),
    "department-rules": (models.DepartmentSchedulingRule, "department_id", True),
    "programs": (models.Program, "department_id", False),
    "years": (models.AcademicYear, None, False),
    "semesters": (models.Semester, "program__department_id", False),
    "sections": (models.Section, "semester__program__department_id", False),
    "subjects": (models.Subject, "semester__program__department_id", True),
    "faculty": (models.FacultyProfile, "department_id", True),
    "students": (
        models.StudentProfile,
        "section__semester__program__department_id",
        False,
    ),
    "department-access": (models.DepartmentAccess, "department_id", False),
    "rooms": (models.Room, None, False),
    "periods": (models.Period, None, False),
    "settings": (models.InstitutionSettings, None, False),
    "assignments": (
        models.FacultySubjectAssignment,
        "subject__semester__program__department_id",
        True,
    ),
    "availability": (models.FacultyAvailability, "faculty__department_id", True),
    "leave": (models.FacultyLeave, "faculty__department_id", True),
    "room-availability": (models.RoomAvailability, None, False),
}


def queryset_for(model, user):
    entry = next((v for v in REGISTRY.values() if v[0] == model), None)
    qs = model.objects.all()
    if user.is_institution_admin:
        return qs
    if entry and entry[1]:
        return scoped(qs, user, entry[1])
    if entry and entry[0] in [
        models.AcademicYear,
        models.Room,
        models.Period,
        models.InstitutionSettings,
    ]:
        return qs
    return qs.none()


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def records(request, resource, pk=None):
    if resource not in REGISTRY:
        raise Http404
    if not request.user.is_institution_admin and request.user.role != "HOD":
        raise PermissionDenied
    model, _, hod_write = REGISTRY[resource]
    qs = queryset_for(model, request.user)
    instance = None
    if pk is not None:
        instance = qs.filter(pk=pk).first()
        if instance is None:
            raise Http404
    Form = forms.modelform_factory(model, exclude=[])
    form = Form(instance=instance)
    # Restrict all relationship choices as well as the object being edited.
    for field in form.fields.values():
        if isinstance(field, forms.ModelChoiceField):
            related = field.queryset.model
            if related._meta.label == "accounts.User":
                if not request.user.is_institution_admin:
                    field.queryset = related.objects.filter(
                        facultyprofile__department_id__in=models.DepartmentAccess.objects.filter(
                            user=request.user
                        ).values(
                            "department_id"
                        )
                    )
            else:
                field.queryset = queryset_for(related, request.user)
    writable = request.user.is_institution_admin or hod_write
    # HODs may not reassign account identity or transfer a faculty profile.
    if resource == "faculty" and not request.user.is_institution_admin:
        form.fields["user"].disabled = True
        form.fields["department"].disabled = True
        if request.method in ["POST", "DELETE"]:
            raise PermissionDenied
    if request.method == "GET":
        fields = []
        for name, field in form.fields.items():
            kind = "text"
            if isinstance(field, forms.BooleanField):
                kind = "checkbox"
            elif isinstance(field, forms.DateField):
                kind = "date"
            elif isinstance(field, forms.TimeField):
                kind = "time"
            elif isinstance(field, forms.IntegerField):
                kind = "number"
            elif isinstance(field, forms.JSONField):
                kind = "json"
            choices = None
            if isinstance(field, forms.ModelChoiceField):
                choices = [[o.pk, str(o)] for o in field.queryset]
            elif isinstance(field, forms.ChoiceField):
                choices = list(field.choices)
            initial = field.initial() if callable(field.initial) else field.initial
            fields.append(
                {
                    "name": name,
                    "label": str(field.label),
                    "required": field.required,
                    "kind": kind,
                    "choices": choices,
                    "initial": initial,
                    "disabled": field.disabled,
                }
            )
        rows = list(qs.values()[:1000])
        return JsonResponse(
            {
                "fields": fields,
                "rows": rows,
                "writable": writable,
                "can_create": writable
                and not (
                    resource == "faculty" and not request.user.is_institution_admin
                ),
                "can_delete": writable
                and not (
                    resource == "faculty" and not request.user.is_institution_admin
                ),
            }
        )
    if not writable:
        raise PermissionDenied
    try:
        with transaction.atomic():
            from timetables.services import lock_scheduler, audit, ScheduleConflict
            from timetables.validators import validate_schedule
            from timetables.models import Timetable

            lock_scheduler()
            if request.method == "DELETE":
                if instance is None:
                    raise Http404
                audit(request.user, instance, "delete")
                instance.delete()
                for official in Timetable.objects.filter(
                    status="PUBLISHED"
                ).select_related(
                    "section__semester__program__department", "section__academic_year"
                ):
                    issues = validate_schedule(
                        official,
                        list(
                            official.entries.select_related(
                                "subject", "faculty__user", "room", "period"
                            )
                        ),
                        complete=True,
                    )
                    if any(i["severity"] == "error" for i in issues):
                        raise ValidationError(
                            "Deletion would invalidate a published timetable."
                        )
                return JsonResponse({"deleted": True})
            if request.method == "PUT" and instance is None:
                raise Http404
            if request.method == "POST" and instance is not None:
                raise Http404
            payload = json.loads(request.body)
            if not isinstance(payload, dict):
                return JsonResponse(
                    {"errors": {"__all__": ["Expected an object."]}}, status=400
                )
            bound = Form(payload, instance=instance)
            for name in form.fields:
                bound.fields[name].disabled = form.fields[name].disabled
                if isinstance(form.fields[name], forms.ModelChoiceField):
                    bound.fields[name].queryset = form.fields[name].queryset
            if not bound.is_valid():
                return JsonResponse({"errors": bound.errors}, status=400)
            obj = bound.save()
            # Master-data changes cannot silently invalidate an official schedule.
            for official in Timetable.objects.filter(status="PUBLISHED").select_related(
                "section__semester__program__department", "section__academic_year"
            ):
                issues = validate_schedule(
                    official,
                    list(
                        official.entries.select_related(
                            "subject", "faculty__user", "room", "period"
                        )
                    ),
                    complete=True,
                )
                if any(i["severity"] == "error" for i in issues):
                    raise ValidationError(
                        "This change would invalidate a published timetable. Withdraw or revise affected schedules first."
                    )
            audit(request.user, obj, "update" if pk else "create")
            return JsonResponse(
                {"id": obj.pk}, status=201 if request.method == "POST" else 200
            )
    except (ValueError, ValidationError, IntegrityError, ProtectedError) as exc:
        return JsonResponse(
            {
                "errors": {
                    "__all__": [
                        "Invalid data or record is referenced by other records."
                    ]
                }
            },
            status=400,
        )
