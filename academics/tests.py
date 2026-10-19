import json
from django.test import TestCase
from accounts.models import User
from .models import (
    Department,
    DepartmentAccess,
    Program,
    AcademicYear,
    Semester,
    Subject,
)


class AcademicTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", role="ADMIN")
        self.hod = User.objects.create_user("hod", role="HOD")
        self.d1 = Department.objects.create(code="CS", name="Computer Science")
        self.d2 = Department.objects.create(code="COM", name="Commerce")
        DepartmentAccess.objects.create(user=self.hod, department=self.d1)
        self.p1 = Program.objects.create(code="BCA", name="BCA", department=self.d1)
        self.p2 = Program.objects.create(code="BCOM", name="B.Com", department=self.d2)
        self.s1 = Semester.objects.create(program=self.p1, number=1, name="I")
        self.s2 = Semester.objects.create(program=self.p2, number=1, name="I")

    def post(self, resource, data):
        return self.client.post(
            "/api/academic/" + resource + "/",
            json.dumps(data),
            content_type="application/json",
        )

    def test_admin_crud_and_duplicates(self):
        self.client.force_login(self.admin)
        result = self.post(
            "departments", {"code": "AI", "name": "AI and Data Science", "active": True}
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(
            self.post("departments", {"code": "AI", "name": "Duplicate"}).status_code,
            400,
        )
        url = f"/api/academic/departments/{result.json()['id']}/"
        self.assertEqual(
            self.client.put(
                url,
                json.dumps({"code": "AI", "name": "AI", "active": True}),
                content_type="application/json",
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(url).status_code, 200)

    def test_hod_relationship_scope(self):
        self.client.force_login(self.hod)
        data = {
            "code": "T1",
            "name": "Test",
            "semester": self.s2.pk,
            "subject_type": "THEORY",
            "weekly_periods": 4,
            "consecutive_periods": 1,
            "required_room_type": "CLASSROOM",
            "equipment": "[]",
            "active": True,
        }
        self.assertEqual(self.post("subjects", data).status_code, 400)
        data["semester"] = self.s1.pk
        self.assertEqual(self.post("subjects", data).status_code, 201)
        ids = [
            r["id"] for r in self.client.get("/api/academic/programs/").json()["rows"]
        ]
        self.assertEqual(ids, [self.p1.pk])
        self.assertEqual(
            self.post("departments", {"code": "X", "name": "X"}).status_code, 403
        )

    def test_read_only_roles_cannot_access_private_master_data(self):
        for role in ["STUDENT", "FACULTY"]:
            self.hod.role = role
            self.hod.save()
            self.client.force_login(self.hod)
            self.assertEqual(self.client.get("/api/academic/faculty/").status_code, 403)
            self.assertEqual(
                self.post("departments", {"code": "X", "name": "X"}).status_code, 403
            )

    def test_invalid_year_dates(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.post(
                "years",
                {
                    "code": "2026",
                    "name": "2026–27",
                    "starts_on": "2027-01-01",
                    "ends_on": "2026-01-01",
                },
            ).status_code,
            400,
        )

    def test_missing_profile_relationship_returns_validation_error(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.post(
                "faculty", {"department": self.d1.pk, "max_weekly_periods": 20}
            ).status_code,
            400,
        )
