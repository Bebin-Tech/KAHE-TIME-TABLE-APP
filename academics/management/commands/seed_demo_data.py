"""Create isolated, editable sample records without replacing existing data."""

import secrets
import uuid
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from academics.models import (
    AcademicYear,
    Department,
    DepartmentAccess,
    FacultyAvailability,
    FacultyLeave,
    FacultyProfile,
    FacultyRequest,
    FacultySubjectAssignment,
    InstitutionSettings,
    Period,
    Program,
    Room,
    RoomAvailability,
    Section,
    Semester,
    StudentProfile,
    Subject,
)
from timetables.models import Timetable
from timetables.services import (
    ScheduleConflict,
    audit,
    create_draft,
    lock_scheduler,
    save_entries,
    transition,
)
from timetables.validators import validate_schedule


class Command(BaseCommand):
    help = "Add labeled development samples, preserving existing accounts and edits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin",
            default="admin",
            help="Existing active institution administrator.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Sample data is restricted to DEBUG=true development environments."
            )
        actor = User.objects.filter(username=options["admin"], is_active=True).first()
        if not actor or not actor.is_institution_admin:
            raise CommandError("Select an existing active administrator with --admin.")
        lock_scheduler()
        institution, _ = InstitutionSettings.objects.get_or_create(
            pk=1,
            defaults={
                "name": "Arts and Science College",
                "working_days": [0, 1, 2, 3, 4],
            },
        )
        if not set(range(5)).issubset(institution.working_days):
            raise CommandError(
                "These samples require Monday–Friday working days; existing settings were preserved."
            )
        if not Period.objects.exists():
            for name, start, end, is_break in [
                ("P1", "09:00", "10:00", False),
                ("P2", "10:00", "11:00", False),
                ("Interval", "11:00", "11:15", True),
                ("P3", "11:15", "12:15", False),
                ("Lunch", "12:15", "13:00", True),
                ("P4", "13:00", "14:00", False),
                ("P5", "14:00", "15:00", False),
            ]:
                Period.objects.create(
                    name=name, starts_at=start, ends_at=end, is_break=is_break
                )
        periods = list(
            Period.objects.filter(is_break=False).order_by("starts_at", "pk")[:5]
        )
        if (
            len(periods) != 5
            or periods[0].ends_at != periods[1].starts_at
            or periods[3].ends_at != periods[4].starts_at
        ):
            raise CommandError(
                "Samples require five teaching periods with contiguous first/last pairs; settings were preserved."
            )

        def record(model, lookup, defaults):
            obj, created = model.objects.get_or_create(**lookup, defaults=defaults)
            if created:
                obj.full_clean()
                audit(actor, obj, "sample_create")
            return obj

        department = record(
            Department, {"code": "DEMO-CS"}, {"name": "Sample Computer Science"}
        )
        program = record(
            Program,
            {"code": "DEMO-BCA"},
            {"name": "BCA — Sample Testing", "department": department},
        )
        year = record(
            AcademicYear,
            {"code": "DEMO-2026-27"},
            {
                "name": "Sample 2026–2027",
                "starts_on": date(2026, 6, 1),
                "ends_on": date(2027, 5, 31),
            },
        )
        semester = record(
            Semester, {"program": program, "number": 1}, {"name": "I — Sample"}
        )
        sections = {
            name: record(
                Section,
                {"semester": semester, "academic_year": year, "name": name},
                {"size": 30},
            )
            for name in ["A", "B"]
        }
        password = secrets.token_urlsafe(18)
        new_users = []

        def account(username, role, first, last):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "first_name": first,
                    "last_name": last,
                    "email": username + "@example.invalid",
                    "is_active": True,
                },
            )
            if created:
                user.set_password(password)
                user.full_clean()
                user.save()
                new_users.append(username)
                audit(actor, user, "sample_account_create", {"role": role})
            elif user.role != role:
                raise CommandError(
                    f"{username} already exists with a different role; no account was overwritten."
                )
            return user

        hod = account("demo.hod", "HOD", "Priya", "Sample HOD")
        record(
            DepartmentAccess,
            {"user": hod, "department": department},
            {"can_publish": False},
        )
        teachers = {}
        for key, username, first, last in [
            ("PY", "demo.faculty01", "Ananya", "Sample"),
            ("MATH", "demo.faculty02", "Arun", "Sample"),
            ("WEB", "demo.faculty03", "Meera", "Sample"),
            ("LAB", "demo.faculty04", "Kavin", "Sample"),
            ("ENG", "demo.hod", "Priya", "Sample HOD"),
        ]:
            user = hod if key == "ENG" else account(username, "FACULTY", first, last)
            teachers[key] = record(
                FacultyProfile,
                {"user": user},
                {"department": department, "max_weekly_periods": 24},
            )
        for number in range(1, 13):
            student = account(
                f"demo.student{number:02}", "STUDENT", "Sample Student", f"{number:02}"
            )
            record(
                StudentProfile,
                {"user": student},
                {
                    "section": sections["A" if number <= 6 else "B"],
                    "registration_number": f"DEMO-2026-{number:03}",
                },
            )

        subjects = {}
        for key, name, weekly, duration, subject_type in [
            ("PY", "Python Programming", 5, 1, "THEORY"),
            ("MATH", "Discrete Mathematics", 5, 1, "THEORY"),
            ("WEB", "Web Technology", 5, 1, "THEORY"),
            ("ENG", "Communication English", 4, 1, "THEORY"),
            ("LAB", "Programming Laboratory", 6, 2, "PRACTICAL"),
        ]:
            subjects[key] = record(
                Subject,
                {"code": "DEMO-" + key},
                {
                    "name": name + " — Sample",
                    "semester": semester,
                    "subject_type": subject_type,
                    "weekly_periods": weekly,
                    "consecutive_periods": duration,
                    "required_room_type": "LAB" if key == "LAB" else "CLASSROOM",
                    "equipment": ["computers"] if key == "LAB" else [],
                },
            )
            record(
                FacultySubjectAssignment,
                {
                    "faculty": teachers[key],
                    "subject": subjects[key],
                    "academic_year": year,
                },
                {},
            )
        rooms = {
            name: record(
                Room,
                {"code": "DEMO-" + name},
                {
                    "name": "Sample "
                    + ("Computer Laboratory" if name == "LAB" else "Classroom " + name),
                    "room_type": "LAB" if name == "LAB" else "CLASSROOM",
                    "capacity": 40,
                    "equipment": ["computers"] if name == "LAB" else ["projector"],
                },
            )
            for name in ["A101", "B101", "LAB"]
        }
        # Shared faculty/lab are deliberately scheduled at different times across sections.
        plans = {
            "A": [
                ["PY", "MATH", "WEB", "LAB", "LAB"],
                ["PY", "MATH", "WEB", "ENG", "PY"],
                ["MATH", "WEB", "ENG", "LAB", "LAB"],
                ["PY", "MATH", "WEB", "ENG", "MATH"],
                ["PY", "WEB", "ENG", "LAB", "LAB"],
            ],
            "B": [
                ["LAB", "LAB", "PY", "MATH", "ENG"],
                ["MATH", "WEB", "ENG", "PY", "MATH"],
                ["LAB", "LAB", "PY", "WEB", "ENG"],
                ["MATH", "WEB", "ENG", "PY", "WEB"],
                ["LAB", "LAB", "MATH", "PY", "WEB"],
            ],
        }

        def request_id(label):
            return uuid.uuid5(uuid.NAMESPACE_URL, "ctms/sample-data/v1/" + label)

        def payload(section_name):
            result = []
            for day, row in enumerate(plans[section_name]):
                for index, key in enumerate(row):
                    if key == "LAB" and index > 0 and row[index - 1] == "LAB":
                        continue
                    result.append(
                        {
                            "subject": subjects[key].pk,
                            "faculty": teachers[key].pk,
                            "room": rooms[
                                "LAB" if key == "LAB" else section_name + "101"
                            ].pk,
                            "day": day,
                            "period": periods[index].pk,
                            "duration": subjects[key].consecutive_periods,
                        }
                    )
            return result

        def publish(table):
            for action in ["submit", "approve", "publish"]:
                table = transition(
                    actor,
                    table.pk,
                    table.revision,
                    action,
                    "Sample-data workflow for application testing.",
                )
            return table

        try:
            initial = Timetable.objects.filter(
                request_id=request_id("A/official-v1")
            ).first()
            if not initial:
                initial = create_draft(
                    actor, sections["A"].pk, request_id("A/official-v1")
                )
                initial, _ = save_entries(
                    actor, initial.pk, initial.revision, payload("A")
                )
                initial = publish(initial)
            official = Timetable.objects.filter(
                request_id=request_id("A/official-v2")
            ).first()
            if not official:
                official = create_draft(
                    actor, sections["A"].pk, request_id("A/official-v2"), initial.pk
                )
                official = publish(official)
            draft = Timetable.objects.filter(
                request_id=request_id("A/editable")
            ).first()
            if not draft:
                draft = create_draft(
                    actor, sections["A"].pk, request_id("A/editable"), official.pk
                )
                editable = [
                    e
                    for e in payload("A")
                    if not (e["day"] == 4 and e["subject"] == subjects["ENG"].pk)
                ]
                draft, _ = save_entries(actor, draft.pk, draft.revision, editable)
            review = Timetable.objects.filter(request_id=request_id("B/review")).first()
            if not review:
                review = create_draft(actor, sections["B"].pk, request_id("B/review"))
                review, _ = save_entries(
                    actor, review.pk, review.revision, payload("B")
                )
                review = transition(
                    actor,
                    review.pk,
                    review.revision,
                    "submit",
                    "Sample section B ready for admin review.",
                )
            for table in [official, draft, review]:
                issues = validate_schedule(
                    table,
                    list(
                        table.entries.select_related(
                            "subject", "faculty__user", "room", "period"
                        )
                    ),
                    complete=table.status != "DRAFT",
                )
                if any(issue["severity"] == "error" for issue in issues):
                    raise ScheduleConflict(issues)
        except ScheduleConflict as exc:
            raise CommandError(
                "Sample schedules were rolled back: "
                + "; ".join(
                    i["message"] for i in exc.issues if i["severity"] == "error"
                )
            ) from exc

        record(
            FacultyAvailability,
            {
                "faculty": teachers["WEB"],
                "day": 4,
                "starts_at": periods[-1].ends_at,
                "ends_at": "17:00",
                "available": False,
            },
            {},
        )
        record(
            RoomAvailability,
            {
                "room": rooms["LAB"],
                "day": 1,
                "starts_at": periods[-1].ends_at,
                "ends_at": "17:00",
                "available": False,
            },
            {},
        )
        record(
            FacultyLeave,
            {
                "faculty": teachers["LAB"],
                "starts_on": date(2026, 10, 24),
                "ends_on": date(2026, 10, 24),
            },
            {"reason": "Sample approved weekend leave", "approved": True},
        )
        record(
            FacultyRequest,
            {
                "faculty": teachers["PY"],
                "kind": "CONFLICT",
                "message": "Sample request: please review projector availability before the next programming class.",
            },
            {},
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Sample data ready: DEMO-CS / DEMO-BCA / DEMO-2026-27. Existing data and passwords preserved."
            )
        )
        for table in [initial, official, draft, review]:
            table.refresh_from_db()
            self.stdout.write(
                f"Section {table.section.name}: v{table.version} {table.status}, {table.entries.count()} sessions"
            )
        self.stdout.write(
            "Section A draft intentionally has one empty Friday slot: add Communication English there, then save and submit."
        )
        if new_users:
            self.stdout.write("New sample accounts: " + ", ".join(new_users))
            self.stdout.write(
                "Temporary password for these NEW sample accounts: " + password
            )
        else:
            self.stdout.write(
                "No new accounts; existing sample passwords were not changed."
            )
