import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from academics.models import (
    DepartmentAccess,
    FacultyProfile,
    FacultySubjectAssignment,
    InstitutionSettings,
    Period,
    Room,
    Section,
)
from .models import Notification, TimetableChangeLog
from .selectors import visible_timetables, visible_entries
from .services import (
    ScheduleConflict,
    StaleRevision,
    create_draft,
    save_entries,
    transition,
)


def serialize(table, user):
    entries = [
        {
            "id": e.pk,
            "subject": e.subject_id,
            "subject_name": e.subject.name,
            "subject_code": e.subject.code,
            "faculty": e.faculty_id,
            "faculty_name": str(e.faculty),
            "room": e.room_id,
            "room_name": e.room.code,
            "day": e.day,
            "period": e.period_id,
            "duration": e.duration,
            "starts_at": str(e.period.starts_at),
        }
        for e in visible_entries(table, user)
    ]
    return {
        "id": table.pk,
        "section": table.section_id,
        "section_name": str(table.section),
        "department": table.section.semester.program.department.name,
        "program": table.section.semester.program.name,
        "semester": table.section.semester.name,
        "year": table.section.academic_year.code,
        "status": table.status,
        "version": table.version,
        "revision": table.revision,
        "entries": entries,
        "history": (
            list(
                table.history.values(
                    "previous_state",
                    "new_state",
                    "comments",
                    "created_at",
                    "actor__username",
                )
            )
            if user.is_institution_admin or user.role == "HOD"
            else []
        ),
    }


@login_required
@require_http_methods(["GET", "POST"])
def tables(request, pk=None):
    if request.method == "GET":
        qs = visible_timetables(request.user)
        if pk:
            table = qs.filter(pk=pk).first()
            if not table:
                raise Http404
            return JsonResponse(serialize(table, request.user))
        return JsonResponse(
            {
                "timetables": [
                    serialize(t, request.user) for t in qs.order_by("-created_at")
                ]
            }
        )
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        if pk is None:
            table = create_draft(
                request.user, data["section"], data["request_id"], data.get("parent")
            )
            return JsonResponse(serialize(table, request.user), status=201)
        # Visibility checked before dispatch; mutation services repeat authorization.
        if not visible_timetables(request.user).filter(pk=pk).exists():
            raise Http404
        action = data.get("action", "save")
        if action in ["save", "validate", "check"]:
            table, issues = save_entries(
                request.user,
                pk,
                data["revision"],
                data["entries"],
                validate_only=action != "save",
                complete=action == "validate",
            )
            return JsonResponse(
                {"timetable": serialize(table, request.user), "issues": issues}
            )
        table = transition(
            request.user, pk, data["revision"], action, str(data.get("comment", ""))
        )
        return JsonResponse({"timetable": serialize(table, request.user), "issues": []})
    except ScheduleConflict as exc:
        return JsonResponse(
            {"errors": "Schedule validation failed.", "issues": exc.issues}, status=422
        )
    except StaleRevision as exc:
        return JsonResponse({"errors": str(exc)}, status=409)
    except (
        ValueError,
        KeyError,
        TypeError,
        ValidationError,
        ObjectDoesNotExist,
    ) as exc:
        return JsonResponse(
            {
                "errors": (
                    exc.messages
                    if isinstance(exc, ValidationError)
                    else "Invalid or missing scheduling data."
                )
            },
            status=400,
        )


@login_required
def editor_config(request):
    if not request.user.is_institution_admin and request.user.role != "HOD":
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    sections = Section.objects.select_related(
        "semester__program__department", "academic_year"
    )
    assignments = FacultySubjectAssignment.objects.select_related(
        "subject", "faculty__user"
    )
    access = DepartmentAccess.objects.filter(user=request.user)
    if not request.user.is_institution_admin:
        sections = sections.filter(
            semester__program__department_id__in=access.values("department_id")
        )
        assignments = assignments.filter(
            subject__semester__program__department_id__in=access.values("department_id")
        )
    settings = InstitutionSettings.objects.first()
    return JsonResponse(
        {
            "sections": [
                {
                    "id": s.pk,
                    "name": str(s),
                    "semester": s.semester_id,
                    "year": s.academic_year_id,
                    "department": s.semester.program.department_id,
                    "can_publish": request.user.is_institution_admin
                    or access.filter(
                        department_id=s.semester.program.department_id, can_publish=True
                    ).exists(),
                }
                for s in sections
            ],
            "assignments": [
                {
                    "id": a.pk,
                    "subject": a.subject_id,
                    "faculty": a.faculty_id,
                    "name": str(a),
                    "semester": a.subject.semester_id,
                    "year": a.academic_year_id,
                    "duration": a.subject.consecutive_periods,
                    "weekly_periods": a.subject.weekly_periods,
                    "room_type": a.subject.required_room_type,
                }
                for a in assignments.filter(
                    subject__active=True, faculty__user__is_active=True
                )
            ],
            "rooms": list(
                Room.objects.filter(active=True).values(
                    "id", "code", "name", "room_type", "capacity"
                )
            ),
            "periods": list(Period.objects.values()),
            "working_days": settings.working_days if settings else [],
            "require_approval": settings.require_approval if settings else True,
            "timezone": settings.timezone if settings else "Asia/Kolkata",
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
def notifications(request):
    if request.method == "POST":
        Notification.objects.filter(user=request.user, read=False).update(read=True)
    return JsonResponse(
        {
            "notifications": list(
                Notification.objects.filter(user=request.user)
                .order_by("-created_at")
                .values("id", "message", "read", "created_at")[:200]
            )
        }
    )


@login_required
def audit_log(request):
    if not request.user.is_institution_admin:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    return JsonResponse(
        {
            "logs": list(
                TimetableChangeLog.objects.select_related("actor")
                .order_by("-created_at")
                .values(
                    "id",
                    "actor__username",
                    "object_type",
                    "object_id",
                    "action",
                    "details",
                    "created_at",
                )[:500]
            )
        }
    )


@login_required
def periods(request):
    return JsonResponse(
        {
            "periods": list(Period.objects.values()),
            "working_days": (
                InstitutionSettings.objects.first().working_days
                if InstitutionSettings.objects.exists()
                else []
            ),
        }
    )


@login_required
def dashboard(request):
    from django.utils import timezone
    from collections import Counter
    from zoneinfo import ZoneInfo

    settings = InstitutionSettings.objects.first()
    now = timezone.now().astimezone(
        ZoneInfo(settings.timezone if settings else "Asia/Kolkata")
    )
    tables = visible_timetables(request.user)
    counts = Counter(tables.values_list("status", flat=True))
    today = []
    for table in tables.filter(status="PUBLISHED"):
        for e in visible_entries(table, request.user).filter(day=now.weekday()):
            today.append(
                {
                    "section": str(table.section),
                    "subject": e.subject.name,
                    "faculty": str(e.faculty),
                    "room": e.room.code,
                    "starts_at": str(e.period.starts_at),
                    "duration": e.duration,
                }
            )
    return JsonResponse(
        {
            "institution": settings.name if settings else "College Timetable",
            "date": now.date().isoformat(),
            "timezone": str(now.tzinfo),
            "counts": dict(counts),
            "unread_notifications": Notification.objects.filter(
                user=request.user, read=False
            ).count(),
            "today": sorted(today, key=lambda r: r["starts_at"]),
        }
    )


@login_required
def conflicts(request):
    if not request.user.is_institution_admin and request.user.role != "HOD":
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    from .validators import validate_schedule

    rows = []
    for table in visible_timetables(request.user).exclude(status="ARCHIVED"):
        for issue in validate_schedule(
            table,
            list(
                table.entries.select_related(
                    "subject", "faculty__user", "room", "period"
                )
            ),
            complete=True,
        ):
            rows.append({"timetable": table.pk, "version": table.version, **issue})
    return JsonResponse({"rows": rows})
