import uuid
from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from accounts.models import User
from academics.models import *
from .models import Timetable, TimetableEntry, Notification, TimetableChangeLog
from .services import (
    create_draft,
    save_entries,
    transition,
    ScheduleConflict,
    StaleRevision,
)


class SchedulingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", role="ADMIN")
        self.hod = User.objects.create_user("hod", role="HOD")
        self.teacher = User.objects.create_user("teacher", role="FACULTY")
        self.student = User.objects.create_user("student", role="STUDENT")
        self.department = Department.objects.create(code="CS", name="Computer Science")
        self.other = Department.objects.create(code="COM", name="Commerce")
        DepartmentAccess.objects.create(user=self.hod, department=self.department)
        self.program = Program.objects.create(
            code="BCA", name="BCA", department=self.department
        )
        self.sem = Semester.objects.create(program=self.program, number=1, name="I")
        self.year = AcademicYear.objects.create(
            code="26", name="2026–27", starts_on="2026-06-01", ends_on="2027-05-31"
        )
        self.year.refresh_from_db()
        self.section = Section.objects.create(
            semester=self.sem, academic_year=self.year, name="A", size=30
        )
        self.section2 = Section.objects.create(
            semester=self.sem, academic_year=self.year, name="B", size=30
        )
        StudentProfile.objects.create(
            user=self.student, section=self.section, registration_number="001"
        )
        self.faculty = FacultyProfile.objects.create(
            user=self.teacher, department=self.department, max_weekly_periods=20
        )
        self.subject = Subject.objects.create(
            code="CS1",
            name="Programming",
            semester=self.sem,
            subject_type="THEORY",
            weekly_periods=1,
        )
        FacultySubjectAssignment.objects.create(
            faculty=self.faculty, subject=self.subject, academic_year=self.year
        )
        self.room = Room.objects.create(
            code="R1", name="Room 1", capacity=40, room_type="CLASSROOM"
        )
        self.period = Period.objects.create(
            name="P1", starts_at="09:00", ends_at="10:00"
        )
        self.p2 = Period.objects.create(name="P2", starts_at="10:00", ends_at="11:00")
        InstitutionSettings.objects.create(working_days=[0, 1, 2, 3, 4])
        self.table = create_draft(self.hod, self.section.pk, uuid.uuid4())

    def entry(self, **overrides):
        return {
            "subject": self.subject.pk,
            "faculty": self.faculty.pk,
            "room": self.room.pk,
            "day": 0,
            "period": self.period.pk,
            "duration": 1,
            **overrides,
        }

    def save(self, entries=None, table=None, revision=0):
        return save_entries(
            self.admin,
            (table or self.table).pk,
            revision,
            entries if entries is not None else [self.entry()],
        )

    def assert_conflict(self, entries, kind, table=None):
        with self.assertRaises(ScheduleConflict) as result:
            self.save(entries, table)
        self.assertIn(kind, [i["type"] for i in result.exception.issues])

    def test_add_move_delete_and_stale_revision(self):
        table, _ = self.save()
        self.assertEqual(table.entries.count(), 1)
        with self.assertRaises(StaleRevision):
            self.save()
        self.save([self.entry(day=1)], revision=1)
        self.assertEqual(self.table.entries.get().day, 1)
        self.save([], revision=2)
        self.assertFalse(self.table.entries.exists())

    def test_section_overlap_uses_actual_times_and_rolls_back(self):
        overlap = Period.objects.create(
            name="Different number", starts_at="09:30", ends_at="10:30"
        )
        self.assert_conflict(
            [self.entry(), self.entry(period=overlap.pk)], "section_overlap"
        )
        self.assertFalse(self.table.entries.exists())

    def test_cross_section_faculty_and_room_conflicts(self):
        self.save()
        table2 = create_draft(self.admin, self.section2.pk, uuid.uuid4())
        self.assert_conflict([self.entry()], "faculty_overlap", table2)
        self.assert_conflict([self.entry()], "room_overlap", table2)

    def test_eligibility_capacity_equipment(self):
        FacultySubjectAssignment.objects.all().delete()
        self.room.capacity = 10
        self.room.save()
        self.subject.equipment = ["GPU"]
        self.subject.save()
        for kind in ["eligibility", "capacity", "room_type"]:
            self.assert_conflict([self.entry()], kind)

    def test_room_availability_and_department_limits(self):
        RoomAvailability.objects.create(
            room=self.room, day=0, starts_at="09:00", ends_at="10:00", available=False
        )
        self.assert_conflict([self.entry()], "room_availability")
        RoomAvailability.objects.all().delete()
        self.subject.weekly_periods = 2
        self.subject.save()
        DepartmentSchedulingRule.objects.create(
            department=self.department, max_daily_periods=1
        )
        self.assert_conflict(
            [self.entry(), self.entry(period=self.p2.pk)], "department_daily_limit"
        )

    def test_api_validation_does_not_save_and_rejects_stale(self):
        import json

        self.client.force_login(self.hod)
        payload = {"action": "check", "revision": 0, "entries": [self.entry()]}
        url = f"/api/timetables/{self.table.pk}/"
        self.assertEqual(
            self.client.post(
                url, json.dumps(payload), content_type="application/json"
            ).status_code,
            200,
        )
        self.assertFalse(self.table.entries.exists())
        payload["action"] = "save"
        self.assertEqual(
            self.client.post(
                url, json.dumps(payload), content_type="application/json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                url, json.dumps(payload), content_type="application/json"
            ).status_code,
            409,
        )

    def test_availability_and_leave(self):
        FacultyAvailability.objects.create(
            faculty=self.faculty,
            day=0,
            starts_at="09:15",
            ends_at="10:00",
            available=False,
        )
        self.assert_conflict([self.entry()], "availability")
        FacultyAvailability.objects.all().delete()
        FacultyLeave.objects.create(
            faculty=self.faculty,
            starts_on="2026-06-01",
            ends_on="2026-06-01",
            approved=True,
            reason="Leave",
        )
        self.assert_conflict([self.entry()], "leave")

    def test_practical_consecutive_and_break(self):
        self.subject.subject_type = "PRACTICAL"
        self.subject.consecutive_periods = 2
        self.subject.weekly_periods = 2
        self.subject.required_room_type = "LAB"
        self.subject.save()
        self.room.room_type = "LAB"
        self.room.save()
        self.save([self.entry(duration=2)])
        self.table.refresh_from_db()
        self.p2.is_break = True
        self.p2.save()
        with self.assertRaises(ScheduleConflict):
            self.save([self.entry(duration=2)], revision=self.table.revision)
        self.assertEqual(self.table.entries.get().duration, 2)

    def test_weekly_hours_and_workload(self):
        with self.assertRaises(ScheduleConflict):
            transition(self.admin, self.table.pk, 0, "submit")
        self.faculty.max_weekly_periods = 0
        self.faculty.save()
        self.assert_conflict([self.entry()], "workload")

    def test_workflow_preserves_official_revision_and_notifies(self):
        table, _ = self.save()
        table = transition(self.hod, table.pk, table.revision, "submit")
        with self.assertRaises(PermissionDenied):
            transition(self.hod, table.pk, table.revision, "approve")
        table = transition(self.admin, table.pk, table.revision, "approve")
        with self.assertRaises(PermissionDenied):
            transition(self.hod, table.pk, table.revision, "publish")
        table = transition(self.admin, table.pk, table.revision, "publish")
        self.assertEqual(Notification.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.save(revision=table.revision)
        revision = create_draft(self.hod, self.section.pk, uuid.uuid4(), table.pk)
        self.assertEqual(revision.entries.count(), 1)
        self.assertEqual(Timetable.objects.get(pk=table.pk).status, "PUBLISHED")
        revision = transition(self.hod, revision.pk, 0, "submit")
        revision = transition(self.admin, revision.pk, revision.revision, "approve")
        transition(self.admin, revision.pk, revision.revision, "publish")
        self.assertEqual(Timetable.objects.get(pk=table.pk).status, "ARCHIVED")
        self.assertTrue(TimetableChangeLog.objects.filter(action="publish").exists())

    def test_return_reason_and_idempotent_create(self):
        table, _ = self.save()
        table = transition(self.hod, table.pk, table.revision, "submit")
        with self.assertRaises(ValidationError):
            transition(self.admin, table.pk, table.revision, "return", "")
        table = transition(
            self.admin, table.pk, table.revision, "return", "Please revise"
        )
        self.assertEqual(table.status, "DRAFT")
        self.assertEqual(
            create_draft(self.hod, self.section.pk, table.request_id).pk, table.pk
        )

    def test_cross_department_and_read_only_mutations(self):
        for user in [self.student, self.teacher]:
            with self.assertRaises(PermissionDenied):
                save_entries(user, self.table.pk, 0, [])
        self.program.department = self.other
        self.program.save()
        with self.assertRaises(PermissionDenied):
            save_entries(self.hod, self.table.pk, 0, [])

    def test_schedule_visibility(self):
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(f"/api/timetables/{self.table.pk}/").status_code, 404
        )
        table, _ = self.save()
        for action in ["submit", "approve", "publish"]:
            table = transition(self.admin, table.pk, table.revision, action)
        self.assertEqual(
            self.client.get(f"/api/timetables/{table.pk}/").status_code, 200
        )
        self.assertEqual(self.client.get("/api/editor-config/").status_code, 403)
