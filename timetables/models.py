from django.conf import settings
from django.db import models
from django.db.models import Q


class SchedulerLock(models.Model):
    """Singleton locked by every scheduling mutation to serialize resource checks."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class Timetable(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    revision = models.PositiveIntegerField(default=0)
    request_id = models.UUIDField(unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_timetables",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="modified_timetables",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["section", "version"], name="unique_section_version"
            )
        ]
        indexes = [models.Index(fields=["section", "status"])]


class TimetableEntry(models.Model):
    timetable = models.ForeignKey(
        Timetable, related_name="entries", on_delete=models.CASCADE
    )
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    faculty = models.ForeignKey("academics.FacultyProfile", on_delete=models.PROTECT)
    room = models.ForeignKey("academics.Room", on_delete=models.PROTECT)
    day = models.PositiveSmallIntegerField()
    period = models.ForeignKey("academics.Period", on_delete=models.PROTECT)
    duration = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["timetable", "day", "period"],
                name="unique_timetable_start_slot",
            ),
            models.CheckConstraint(
                condition=Q(day__lte=6, duration__gte=1),
                name="entry_day_duration_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["faculty", "day"]),
            models.Index(fields=["room", "day"]),
        ]


class TimetableApproval(models.Model):
    timetable = models.ForeignKey(
        Timetable, related_name="history", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous_state = models.CharField(max_length=12)
    new_state = models.CharField(max_length=12)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TimetableChangeLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    object_type = models.CharField(max_length=100)
    object_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=500)
    timetable = models.ForeignKey(Timetable, null=True, on_delete=models.SET_NULL)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "read"])]
