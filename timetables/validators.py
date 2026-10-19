from collections import Counter
from datetime import timedelta
from academics.models import (
    FacultyAvailability,
    FacultyLeave,
    FacultySubjectAssignment,
    InstitutionSettings,
    Period,
    Subject,
    RoomAvailability,
    DepartmentSchedulingRule,
)
from .models import TimetableEntry


def interval(entry, periods):
    index = next((i for i, p in enumerate(periods) if p.pk == entry.period_id), -1)
    if index < 0 or entry.duration < 1 or index + entry.duration > len(periods):
        return None
    block = periods[index : index + entry.duration]
    if any(p.is_break for p in block) or any(
        a.ends_at != b.starts_at for a, b in zip(block, block[1:])
    ):
        return None
    return block[0].starts_at, block[-1].ends_at


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def validate_schedule(timetable, entries, complete=False):
    periods = list(Period.objects.order_by("starts_at", "pk"))
    settings = InstitutionSettings.objects.first()
    issues = []

    def issue(kind, entry, message, suggestion, warning=False, conflicting=None):
        issues.append(
            {
                "type": kind,
                "day": entry.day if entry else None,
                "period": entry.period_id if entry else None,
                "section": str(timetable.section),
                "faculty": str(entry.faculty) if entry else None,
                "room": entry.room.code if entry else None,
                "message": message,
                "suggestion": suggestion,
                "severity": "warning" if warning else "error",
                "conflicting_assignment": conflicting,
            }
        )

    if not settings:
        issue(
            "configuration",
            None,
            "Institution settings are required.",
            "Configure working days and scheduling policy.",
        )
        return issues
    year = timetable.section.academic_year
    # Other sections reserve resources in all live versions. Revisions of this section
    # are alternatives, so its old official schedule is excluded from draft validation.
    external = list(
        TimetableEntry.objects.filter(
            timetable__section__academic_year__starts_on__lte=year.ends_on,
            timetable__section__academic_year__ends_on__gte=year.starts_on,
            timetable__status__in=["DRAFT", "SUBMITTED", "APPROVED", "PUBLISHED"],
        )
        .exclude(timetable__section=timetable.section)
        .select_related(
            "period", "subject", "faculty__user", "room", "timetable__section"
        )
    )
    intervals = []
    weekly = Counter()
    workload = Counter()
    # Multiple versions of another section must not multiply workload.
    external_workload = {}
    for other in external:
        key = (other.timetable.section_id, other.faculty_id)
        version_key = (other.timetable_id, key)
        external_workload[version_key] = (
            external_workload.get(version_key, 0) + other.duration
        )
    maxima = {}
    for (_, key), count in external_workload.items():
        maxima[key] = max(maxima.get(key, 0), count)
    for (_, faculty_id), count in maxima.items():
        workload[faculty_id] += count
    for entry in entries:
        weekly[entry.subject_id] += entry.duration
        workload[entry.faculty_id] += entry.duration
        current = interval(entry, periods)
        if entry.subject.semester_id != timetable.section.semester_id:
            issue(
                "academic_scope",
                entry,
                "Subject does not belong to this section semester.",
                "Select a subject for this semester.",
            )
        if (
            not entry.subject.active
            or not entry.room.active
            or not entry.faculty.user.is_active
        ):
            issue(
                "inactive_resource",
                entry,
                "Subject, room or faculty is inactive.",
                "Select active resources.",
            )
        if entry.day not in settings.working_days:
            issue(
                "working_day",
                entry,
                "This is not a working day.",
                "Choose a configured working day.",
            )
        if not current:
            issue(
                "consecutive_periods",
                entry,
                "Session must use consecutive teaching periods without a break or gap.",
                "Choose a continuous block of teaching periods.",
            )
            continue
        if any(
            p.is_break and overlaps(current, (p.starts_at, p.ends_at)) for p in periods
        ):
            issue(
                "break",
                entry,
                "Class overlaps a configured break.",
                "Move the class outside break times.",
            )
        if entry.duration != entry.subject.consecutive_periods:
            issue(
                "duration",
                entry,
                "Duration differs from the required consecutive periods.",
                "Use the configured session duration.",
            )
        if not FacultySubjectAssignment.objects.filter(
            faculty=entry.faculty, subject=entry.subject, academic_year=year
        ).exists():
            issue(
                "eligibility",
                entry,
                "Faculty is not assigned to this subject and year.",
                "Create an eligible faculty assignment.",
            )
        unavailable = FacultyAvailability.objects.filter(
            faculty=entry.faculty, day=entry.day
        )
        allowed = list(unavailable.filter(available=True))
        if any(
            overlaps(current, (a.starts_at, a.ends_at))
            for a in unavailable.filter(available=False)
        ) or (
            allowed
            and not any(
                a.starts_at <= current[0] and current[1] <= a.ends_at for a in allowed
            )
        ):
            issue(
                "availability",
                entry,
                "Faculty is unavailable during this interval.",
                "Choose an available interval.",
            )
        for leave in FacultyLeave.objects.filter(
            faculty=entry.faculty,
            approved=True,
            starts_on__lte=year.ends_on,
            ends_on__gte=year.starts_on,
        ):
            start = max(year.starts_on, leave.starts_on)
            end = min(year.ends_on, leave.ends_on)
            occurrence = start + timedelta(days=(entry.day - start.weekday()) % 7)
            if occurrence <= end:
                issue(
                    "leave",
                    entry,
                    "Approved leave intersects this recurring weekday.",
                    "Choose another faculty member or revise the leave/date configuration.",
                )
                break
        if entry.room.capacity < timetable.section.size:
            issue(
                "capacity",
                entry,
                "Room capacity is smaller than the section.",
                "Choose a larger room.",
            )
        room_windows = RoomAvailability.objects.filter(room=entry.room, day=entry.day)
        room_allowed = list(room_windows.filter(available=True))
        if any(
            overlaps(current, (a.starts_at, a.ends_at))
            for a in room_windows.filter(available=False)
        ) or (
            room_allowed
            and not any(
                a.starts_at <= current[0] and current[1] <= a.ends_at
                for a in room_allowed
            )
        ):
            issue(
                "room_availability",
                entry,
                "Room is unavailable during this interval.",
                "Choose an available room or time.",
            )
        if entry.room.room_type != entry.subject.required_room_type or not set(
            entry.subject.equipment
        ).issubset(set(entry.room.equipment)):
            issue(
                "room_type",
                entry,
                "Room type or required equipment is unsuitable.",
                "Select a suitable classroom or laboratory.",
            )
        for other, other_interval in intervals:
            if entry.day == other.day and overlaps(current, other_interval):
                issue(
                    "section_overlap",
                    entry,
                    "Section has overlapping classes.",
                    "Move or remove the conflicting assignment.",
                    conflicting=other.subject.code,
                )
        for other in external:
            other_interval = interval(other, periods)
            if (
                other.day != entry.day
                or not other_interval
                or not overlaps(current, other_interval)
            ):
                continue
            if other.faculty_id == entry.faculty_id:
                issue(
                    "faculty_overlap",
                    entry,
                    "Faculty is booked in another section.",
                    "Choose another faculty member or interval.",
                    conflicting=f"{other.timetable.section}: {other.subject.code}",
                )
            if other.room_id == entry.room_id:
                issue(
                    "room_overlap",
                    entry,
                    "Room is booked in another section.",
                    "Choose another room or interval.",
                    conflicting=f"{other.timetable.section}: {other.subject.code}",
                )
        intervals.append((entry, current))
    for subject in Subject.objects.filter(
        semester=timetable.section.semester, active=True
    ):
        count = weekly[subject.pk]
        if count != subject.weekly_periods:
            issue(
                "weekly_hours",
                next((e for e in entries if e.subject_id == subject.pk), None),
                f"{subject.code}: scheduled {count}; required {subject.weekly_periods} periods.",
                "Adjust the number of weekly sessions.",
                warning=not (complete and settings.enforce_weekly_hours)
                and count <= subject.weekly_periods,
            )
    for entry in entries:
        if workload[entry.faculty_id] > entry.faculty.max_weekly_periods:
            issue(
                "workload",
                entry,
                f"Faculty workload {workload[entry.faculty_id]} exceeds limit {entry.faculty.max_weekly_periods}.",
                "Reassign sessions or adjust an authorized workload limit.",
            )
    rule = DepartmentSchedulingRule.objects.filter(
        department=timetable.section.semester.program.department
    ).first()
    if rule:
        daily = Counter()
        subject_daily = Counter()
        for entry in entries:
            daily[entry.day] += entry.duration
            subject_daily[(entry.day, entry.subject_id)] += entry.duration
        for day, count in daily.items():
            if rule.max_daily_periods and count > rule.max_daily_periods:
                issue(
                    "department_daily_limit",
                    next(e for e in entries if e.day == day),
                    f"{count} periods exceed the department daily limit {rule.max_daily_periods}.",
                    "Spread sessions across working days.",
                    warning=rule.severity == "WARNING",
                )
        for (day, subject_id), count in subject_daily.items():
            if (
                rule.max_subject_periods_per_day
                and count > rule.max_subject_periods_per_day
            ):
                issue(
                    "department_subject_limit",
                    next(
                        e
                        for e in entries
                        if e.day == day and e.subject_id == subject_id
                    ),
                    f"{count} subject periods exceed the daily limit {rule.max_subject_periods_per_day}.",
                    "Move a session to a different day.",
                    warning=rule.severity == "WARNING",
                )
    return issues
