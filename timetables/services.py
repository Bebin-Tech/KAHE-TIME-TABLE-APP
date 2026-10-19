import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from academics.models import (
    DepartmentAccess,
    FacultyProfile,
    InstitutionSettings,
    Period,
    Room,
    Section,
    Subject,
)
from accounts.models import User
from .models import (
    Notification,
    SchedulerLock,
    Timetable,
    TimetableApproval,
    TimetableChangeLog,
    TimetableEntry,
)
from .validators import validate_schedule


class StaleRevision(Exception):
    pass


class ScheduleConflict(Exception):
    def __init__(self, issues):
        self.issues = issues


def lock_scheduler():
    SchedulerLock.objects.get_or_create(pk=1)
    SchedulerLock.objects.select_for_update().get(pk=1)


def authorize_editor(user, section):
    if user.is_institution_admin:
        return
    if (
        user.role != "HOD"
        or not DepartmentAccess.objects.filter(
            user=user, department=section.semester.program.department
        ).exists()
    ):
        raise PermissionDenied


def audit(user, obj, action, details=None):
    TimetableChangeLog.objects.create(
        actor=user,
        object_type=obj._meta.label,
        object_id=obj.pk,
        action=action,
        details=details or {},
    )


@transaction.atomic
def create_draft(user, section_id, request_id, parent_id=None):
    lock_scheduler()
    section = Section.objects.select_related(
        "semester__program__department", "academic_year"
    ).get(pk=section_id)
    authorize_editor(user, section)
    request_id = uuid.UUID(str(request_id))
    existing = Timetable.objects.filter(request_id=request_id).first()
    if existing:
        if existing.created_by_id != user.pk or existing.section_id != section.pk:
            raise PermissionDenied
        return existing
    parent = None
    if parent_id:
        parent = Timetable.objects.get(pk=parent_id, section=section)
        if parent.status not in ["PUBLISHED", "ARCHIVED"]:
            raise ValidationError("Only official or archived versions can be copied.")
    if Timetable.objects.filter(
        section=section, status__in=["DRAFT", "SUBMITTED", "APPROVED"]
    ).exists():
        raise ValidationError(
            "An active draft or review already exists for this section."
        )
    version = (
        Timetable.objects.filter(section=section).aggregate(v=Max("version"))["v"] or 0
    ) + 1
    table = Timetable.objects.create(
        section=section,
        version=version,
        parent=parent,
        created_by=user,
        modified_by=user,
        request_id=request_id,
    )
    if parent:
        TimetableEntry.objects.bulk_create(
            [
                TimetableEntry(
                    timetable=table,
                    subject=e.subject,
                    faculty=e.faculty,
                    room=e.room,
                    day=e.day,
                    period=e.period,
                    duration=e.duration,
                )
                for e in parent.entries.all()
            ]
        )
    audit(user, table, "create_draft")
    return table


def proposed_entries(table, payload):
    if not isinstance(payload, list) or len(payload) > 500:
        raise ValidationError("Entries must be a list with at most 500 sessions.")
    entries = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValidationError("Each entry must be an object.")
        entry = TimetableEntry(
            timetable=table,
            subject=Subject.objects.select_related("semester").get(pk=raw["subject"]),
            faculty=FacultyProfile.objects.select_related("user").get(
                pk=raw["faculty"]
            ),
            room=Room.objects.get(pk=raw["room"]),
            period=Period.objects.get(pk=raw["period"]),
            day=int(raw["day"]),
            duration=int(raw["duration"]),
        )
        # Validate scalar fields here; multi-row uniqueness is checked against the
        # proposed schedule, not the previous persisted snapshot.
        entry.clean_fields()
        entries.append(entry)
    return entries


@transaction.atomic
def save_entries(
    user, table_id, revision, payload, validate_only=False, complete=False
):
    lock_scheduler()
    table = (
        Timetable.objects.select_for_update()
        .select_related(
            "section__semester__program__department", "section__academic_year"
        )
        .get(pk=table_id)
    )
    authorize_editor(user, table.section)
    if table.status != "DRAFT":
        raise ValidationError(
            "Only drafts can be edited. Create a revision of an official version."
        )
    if revision != table.revision:
        raise StaleRevision("This version changed. Reload before saving.")
    entries = proposed_entries(table, payload)
    issues = validate_schedule(table, entries, complete=complete)
    if any(i["severity"] == "error" for i in issues):
        raise ScheduleConflict(issues)
    if validate_only:
        return table, issues
    before = list(
        table.entries.values(
            "subject_id", "faculty_id", "room_id", "day", "period_id", "duration"
        )
    )
    table.entries.all().delete()
    TimetableEntry.objects.bulk_create(entries)
    table.revision += 1
    table.modified_by = user
    table.save(update_fields=["revision", "modified_by", "modified_at"])
    audit(
        user,
        table,
        "save",
        {"revision": table.revision, "before": before, "after": payload},
    )
    return table, issues


@transaction.atomic
def transition(user, table_id, revision, action, comment=""):
    lock_scheduler()
    table = (
        Timetable.objects.select_for_update()
        .select_related(
            "section__semester__program__department", "section__academic_year"
        )
        .get(pk=table_id)
    )
    authorize_editor(user, table.section)
    if revision != table.revision:
        raise StaleRevision("This version changed. Reload before changing status.")
    settings = InstitutionSettings.objects.first()
    if not settings:
        raise ValidationError("Configure institution settings first.")
    transitions = {
        "submit": ("DRAFT", "SUBMITTED"),
        "approve": ("SUBMITTED", "APPROVED"),
        "return": ("SUBMITTED", "DRAFT"),
        "publish": ("APPROVED", "PUBLISHED"),
        "archive": ("PUBLISHED", "ARCHIVED"),
        "withdraw": ("PUBLISHED", "ARCHIVED"),
    }
    if action not in transitions:
        raise ValidationError("Unknown workflow action.")
    old, new = transitions[action]
    if (
        action == "publish"
        and not settings.require_approval
        and table.status == "DRAFT"
    ):
        old = "DRAFT"
    if table.status != old:
        raise ValidationError(f"{action} requires status {old}.")
    if (
        action in ["approve", "return", "archive", "withdraw"]
        and not user.is_institution_admin
    ):
        raise PermissionDenied
    if action == "return" and not comment.strip():
        raise ValidationError("A correction reason is required.")
    if (
        action == "publish"
        and not user.is_institution_admin
        and not DepartmentAccess.objects.filter(
            user=user,
            department=table.section.semester.program.department,
            can_publish=True,
        ).exists()
    ):
        raise PermissionDenied
    if action in ["submit", "approve", "publish"]:
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
            raise ScheduleConflict(issues)
    if action == "publish":
        prior_faculty_ids = set()
        for previous in Timetable.objects.filter(
            section=table.section, status="PUBLISHED"
        ).exclude(pk=table.pk):
            prior_faculty_ids.update(
                previous.entries.values_list("faculty__user_id", flat=True)
            )
            previous.status = "ARCHIVED"
            previous.revision += 1
            previous.modified_by = user
            previous.save()
            TimetableApproval.objects.create(
                timetable=previous,
                actor=user,
                previous_state="PUBLISHED",
                new_state="ARCHIVED",
                comments="Superseded by a published revision.",
            )
            audit(user, previous, "superseded", {"replacement": table.pk})
    table.status = new
    table.revision += 1
    table.modified_by = user
    table.save()
    TimetableApproval.objects.create(
        timetable=table,
        actor=user,
        previous_state=old,
        new_state=new,
        comments=comment[:4000],
    )
    audit(user, table, action, {"from": old, "to": new, "comment": comment[:4000]})
    if action in ["publish", "withdraw", "archive"]:
        recipient_ids = set(
            User.objects.filter(is_active=True)
            .filter(
                Q(studentprofile__section=table.section)
                | Q(facultyprofile__timetableentry__timetable=table)
            )
            .values_list("id", flat=True)
        )
        if action == "publish":
            recipient_ids.update(
                User.objects.filter(
                    pk__in=prior_faculty_ids, is_active=True
                ).values_list("pk", flat=True)
            )
        Notification.objects.bulk_create(
            [
                Notification(
                    user_id=pk,
                    timetable=table,
                    message=f"{table.section}: timetable v{table.version} {new.lower()}.",
                )
                for pk in recipient_ids
            ]
        )
    return table
