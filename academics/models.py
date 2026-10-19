from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class NamedCode(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=180)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class Department(NamedCode):
    pass


class DepartmentSchedulingRule(models.Model):
    department = models.OneToOneField(Department, on_delete=models.CASCADE)
    max_daily_periods = models.PositiveSmallIntegerField(
        default=0, help_text="Zero disables this limit."
    )
    max_subject_periods_per_day = models.PositiveSmallIntegerField(
        default=0, help_text="Zero disables this limit."
    )
    severity = models.CharField(
        max_length=10,
        choices=[("ERROR", "Hard conflict"), ("WARNING", "Warning")],
        default="ERROR",
    )


class Program(NamedCode):
    department = models.ForeignKey(Department, on_delete=models.PROTECT)


class AcademicYear(NamedCode):
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta(NamedCode.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gt=F("starts_on")), name="year_dates_valid"
            )
        ]


class Semester(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
    number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["program", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "number"], name="unique_program_semester"
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1), name="semester_positive"
            ),
        ]

    def __str__(self):
        return f"{self.program.code} · {self.name}"


class Section(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    name = models.CharField(max_length=40)
    size = models.PositiveIntegerField(default=40)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "academic_year", "name"], name="unique_section_year"
            ),
            models.CheckConstraint(
                condition=Q(size__gte=1), name="section_size_positive"
            ),
        ]

    def __str__(self):
        return f"{self.semester} · {self.name} ({self.academic_year.code})"


class FacultyProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    max_weekly_periods = models.PositiveSmallIntegerField(default=24)

    def clean(self):
        if self.user_id and self.user.role not in ["FACULTY", "HOD"]:
            raise ValidationError({"user": "Select a faculty or HOD account."})

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class DepartmentAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    can_publish = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department"], name="unique_department_access"
            )
        ]

    def clean(self):
        if self.user_id and self.user.role != "HOD":
            raise ValidationError(
                {"user": "Department access is assigned only to HOD accounts."}
            )


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    section = models.ForeignKey(Section, on_delete=models.PROTECT)
    registration_number = models.CharField(max_length=50, unique=True)

    def clean(self):
        if self.user_id and self.user.role != "STUDENT":
            raise ValidationError({"user": "Select a student account."})

    def __str__(self):
        return self.registration_number


class Room(NamedCode):
    room_type = models.CharField(
        max_length=30, choices=[("CLASSROOM", "Classroom"), ("LAB", "Laboratory")]
    )
    capacity = models.PositiveIntegerField()
    equipment = models.JSONField(default=list, blank=True)

    class Meta(NamedCode.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(
                condition=Q(capacity__gte=1), name="room_capacity_positive"
            )
        ]

    def clean(self):
        if not isinstance(self.equipment, list) or any(
            not isinstance(v, str) for v in self.equipment
        ):
            raise ValidationError({"equipment": "Use a JSON list of equipment names."})


class Subject(NamedCode):
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)
    subject_type = models.CharField(
        max_length=20,
        choices=[
            (v, v.title()) for v in ["THEORY", "PRACTICAL", "TUTORIAL", "ELECTIVE"]
        ],
    )
    weekly_periods = models.PositiveSmallIntegerField(default=4)
    consecutive_periods = models.PositiveSmallIntegerField(default=1)
    required_room_type = models.CharField(
        max_length=30,
        choices=Room._meta.get_field("room_type").choices,
        default="CLASSROOM",
    )
    equipment = models.JSONField(default=list, blank=True)

    class Meta(NamedCode.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(
                condition=Q(weekly_periods__gte=1, consecutive_periods__gte=1),
                name="subject_hours_positive",
            )
        ]

    def clean(self):
        if self.consecutive_periods > self.weekly_periods:
            raise ValidationError(
                {"consecutive_periods": "Cannot exceed weekly periods."}
            )
        if not isinstance(self.equipment, list) or any(
            not isinstance(v, str) for v in self.equipment
        ):
            raise ValidationError({"equipment": "Use a JSON list of equipment names."})


class FacultySubjectAssignment(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "subject", "academic_year"],
                name="unique_faculty_subject_year",
            )
        ]

    def __str__(self):
        return f"{self.subject.code} · {self.faculty}"


class Period(models.Model):
    name = models.CharField(max_length=50)
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="period_times_valid"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.starts_at:%H:%M}–{self.ends_at:%H:%M})"


class InstitutionSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=180, default="College Timetable")
    timezone = models.CharField(max_length=80, default="Asia/Kolkata")
    working_days = models.JSONField(default=list)
    require_approval = models.BooleanField(default=True)
    enforce_weekly_hours = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Institution settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(id=1), name="singleton_institution_settings"
            )
        ]

    def clean(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if (
            not isinstance(self.working_days, list)
            or not self.working_days
            or any(type(d) is not int or d not in range(7) for d in self.working_days)
            or len(set(self.working_days)) != len(self.working_days)
        ):
            raise ValidationError(
                {
                    "working_days": "Enter distinct weekdays as a JSON list: Monday=0, Sunday=6."
                }
            )
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({"timezone": "Enter a valid IANA timezone."})
        if InstitutionSettings.objects.exclude(pk=self.pk).exists():
            raise ValidationError("Only one institution settings record is supported.")


class FacultyAvailability(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE)
    day = models.PositiveSmallIntegerField(
        choices=[
            (i, d)
            for i, d in enumerate(
                [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
            )
        ]
    )
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    available = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="availability_times_valid"
            )
        ]


class FacultyLeave(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE)
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.CharField(max_length=250)
    approved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")), name="leave_dates_valid"
            )
        ]


class RoomAvailability(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    day = models.PositiveSmallIntegerField(
        choices=[
            (i, d)
            for i, d in enumerate(
                [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
            )
        ]
    )
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    available = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="room_availability_times_valid",
            )
        ]


class FacultyRequest(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=20,
        choices=[
            ("LEAVE", "Leave"),
            ("UNAVAILABLE", "Unavailable interval"),
            ("CONFLICT", "Scheduling conflict"),
        ],
    )
    message = models.TextField(max_length=2000)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    day = models.PositiveSmallIntegerField(null=True, blank=True)
    starts_at = models.TimeField(null=True, blank=True)
    ends_at = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        default="PENDING",
        choices=[
            ("PENDING", "Pending"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
    )
    response = models.TextField(blank=True, max_length=2000)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.kind == "LEAVE" and (
            not self.starts_on or not self.ends_on or self.ends_on < self.starts_on
        ):
            raise ValidationError("Leave requests require valid start and end dates.")
        if self.kind == "UNAVAILABLE" and (
            self.day not in range(7)
            or not self.starts_at
            or not self.ends_at
            or self.ends_at <= self.starts_at
        ):
            raise ValidationError(
                "Availability requests require a weekday and valid time interval."
            )
