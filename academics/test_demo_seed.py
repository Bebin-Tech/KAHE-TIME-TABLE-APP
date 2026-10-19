from io import StringIO

from django.contrib.auth import authenticate
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from academics.models import FacultyProfile, StudentProfile, Subject
from timetables.models import Notification, Timetable
from timetables.validators import validate_schedule


@override_settings(DEBUG=True)
class DemoSeedTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin", password="Existing-Admin-Password-490!"
        )

    def seed(self):
        output = StringIO()
        call_command("seed_demo_data", stdout=output)
        return output.getvalue()

    def test_real_valid_schedules_accounts_and_permissions(self):
        output = self.seed()
        password = output.split("Temporary password for these NEW sample accounts: ")[
            1
        ].strip()
        self.assertIsNotNone(authenticate(username="demo.hod", password=password))
        self.assertIsNotNone(authenticate(username="demo.student01", password=password))
        self.assertEqual(FacultyProfile.objects.count(), 5)
        self.assertEqual(StudentProfile.objects.count(), 12)
        self.assertEqual(Subject.objects.count(), 5)
        self.assertEqual(Timetable.objects.count(), 4)
        self.assertEqual(Timetable.objects.filter(status="PUBLISHED").count(), 1)
        self.assertEqual(Timetable.objects.filter(status="SUBMITTED").count(), 1)
        for table in Timetable.objects.exclude(status="ARCHIVED"):
            issues = validate_schedule(
                table,
                list(
                    table.entries.select_related(
                        "subject", "faculty__user", "room", "period"
                    )
                ),
                complete=table.status != "DRAFT",
            )
            self.assertFalse(
                [issue for issue in issues if issue["severity"] == "error"]
            )
        draft = Timetable.objects.get(status="DRAFT")
        self.assertEqual(sum(draft.entries.values_list("duration", flat=True)), 24)
        self.assertTrue(
            Notification.objects.filter(user__username="demo.student01").exists()
        )
        self.assertTrue(self.admin.check_password("Existing-Admin-Password-490!"))
        self.client.login(username="demo.student01", password=password)
        schedules = self.client.get("/api/timetables/").json()["timetables"]
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]["status"], "PUBLISHED")
        self.assertEqual(self.client.get("/api/editor-config/").status_code, 403)

    def test_repeat_preserves_passwords_edits_and_versions(self):
        self.seed()
        user = User.objects.get(username="demo.faculty01")
        password_hash = user.password
        subject = Subject.objects.get(code="DEMO-PY")
        subject.name = "User edited this sample subject"
        subject.save()
        table_state = list(Timetable.objects.values_list("pk", "revision", "status"))
        output = self.seed()
        user.refresh_from_db()
        subject.refresh_from_db()
        self.assertEqual(user.password, password_hash)
        self.assertEqual(subject.name, "User edited this sample subject")
        self.assertEqual(
            list(Timetable.objects.values_list("pk", "revision", "status")), table_state
        )
        self.assertIn("No new accounts", output)

    @override_settings(DEBUG=False)
    def test_production_seed_is_refused(self):
        with self.assertRaises(CommandError):
            self.seed()
