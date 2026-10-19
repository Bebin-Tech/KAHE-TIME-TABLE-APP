from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from academics.models import (
    Department,
    Program,
    AcademicYear,
    Semester,
    Section,
    Subject,
    Room,
    Period,
    InstitutionSettings,
)
from timetables.models import SchedulerLock


class Command(BaseCommand):
    help = "Create optional configurable academic examples. Does not create accounts or passwords."

    @transaction.atomic
    def handle(self, *args, **options):
        SchedulerLock.objects.get_or_create(pk=1)
        InstitutionSettings.objects.get_or_create(
            pk=1,
            defaults={
                "name": "Arts and Science College",
                "working_days": [0, 1, 2, 3, 4],
            },
        )
        year, _ = AcademicYear.objects.get_or_create(
            code="2026-27",
            defaults={
                "name": "2026–2027",
                "starts_on": date(2026, 6, 1),
                "ends_on": date(2027, 5, 31),
            },
        )
        for department_code, department_name, program_code, program_name in [
            ("CS", "Computer Science", "BCA", "BCA"),
            (
                "AI",
                "Artificial Intelligence",
                "BSC-AIDS",
                "B.Sc Artificial Intelligence and Data Science",
            ),
            ("COM", "Commerce", "BCOM", "B.Com"),
            ("MGT", "Management", "BBA", "BBA"),
        ]:
            dep, _ = Department.objects.get_or_create(
                code=department_code, defaults={"name": department_name}
            )
            program, _ = Program.objects.get_or_create(
                code=program_code, defaults={"name": program_name, "department": dep}
            )
            for number, name in enumerate(["I", "II", "III", "IV", "V", "VI"], 1):
                semester, _ = Semester.objects.get_or_create(
                    program=program, number=number, defaults={"name": name}
                )
                for section in ["A", "B"]:
                    Section.objects.get_or_create(
                        semester=semester,
                        academic_year=year,
                        name=section,
                        defaults={"size": 40},
                    )
        for name, start, end, is_break in [
            ("P1", "09:00", "10:00", False),
            ("P2", "10:00", "11:00", False),
            ("Interval", "11:00", "11:15", True),
            ("P3", "11:15", "12:15", False),
            ("Lunch", "12:15", "13:00", True),
            ("P4", "13:00", "14:00", False),
            ("P5", "14:00", "15:00", False),
        ]:
            Period.objects.get_or_create(
                name=name, starts_at=start, ends_at=end, defaults={"is_break": is_break}
            )
        Room.objects.get_or_create(
            code="C101",
            defaults={
                "name": "Classroom 101",
                "room_type": "CLASSROOM",
                "capacity": 60,
            },
        )
        Room.objects.get_or_create(
            code="LAB1",
            defaults={
                "name": "Computer laboratory",
                "room_type": "LAB",
                "capacity": 45,
                "equipment": ["computers"],
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Academic examples created. Configure subjects and create accounts through the application."
            )
        )
