import json
from django.test import TestCase
from timetables.tests import SchedulingTests
from .models import FacultyRequest, FacultyAvailability


class FacultyRequestTests(TestCase):
    def setUp(self):
        SchedulingTests.setUp(self)

    def test_own_request_review_and_readonly_student(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            "/api/requests/",
            json.dumps(
                {
                    "kind": "UNAVAILABLE",
                    "message": "Research meeting",
                    "day": 2,
                    "starts_at": "09:00",
                    "ends_at": "10:00",
                    "faculty": 999,
                    "status": "APPROVED",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        obj = FacultyRequest.objects.get(pk=response.json()["id"])
        self.assertEqual(obj.status, "PENDING")
        self.assertEqual(obj.faculty, self.faculty)
        self.assertEqual(
            self.client.post(
                f"/api/requests/{obj.pk}/",
                json.dumps({"status": "APPROVED"}),
                content_type="application/json",
            ).status_code,
            403,
        )
        self.client.force_login(self.hod)
        self.assertEqual(
            self.client.post(
                f"/api/requests/{obj.pk}/",
                json.dumps({"status": "APPROVED"}),
                content_type="application/json",
            ).status_code,
            200,
        )
        self.assertTrue(
            FacultyAvailability.objects.filter(faculty=self.faculty, day=2).exists()
        )
        self.client.force_login(self.student)
        self.assertEqual(self.client.get("/api/requests/").status_code, 403)

    def test_invalid_request(self):
        self.client.force_login(self.teacher)
        self.assertEqual(
            self.client.post(
                "/api/requests/",
                json.dumps(
                    {
                        "kind": "LEAVE",
                        "message": "Leave",
                        "starts_on": "2026-07-10",
                        "ends_on": "2026-07-01",
                    }
                ),
                content_type="application/json",
            ).status_code,
            400,
        )
