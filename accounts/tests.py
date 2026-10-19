from django.test import TestCase, Client
from .models import User


class AuthenticationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            "student", password="Strong-Password-548!"
        )

    def test_login_logout(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "student", "password": "Strong-Password-548!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/session/").json()["role"], "STUDENT")
        self.assertEqual(self.client.post("/accounts/logout/").status_code, 302)
        self.assertEqual(self.client.get("/api/session/").status_code, 302)

    def test_inactive(self):
        self.student.is_active = False
        self.student.save()
        self.assertFalse(
            self.client.login(username="student", password="Strong-Password-548!")
        )

    def test_role_access(self):
        for role in User.Role.values:
            self.student.role = role
            self.student.save()
            self.client.force_login(self.student)
            self.assertEqual(
                self.client.get("/api/users/").status_code,
                200 if role == "ADMIN" else 403,
            )

    def test_csrf(self):
        self.assertEqual(
            Client(enforce_csrf_checks=True).post("/accounts/login/", {}).status_code,
            403,
        )

    def test_password_hashed(self):
        self.assertNotEqual(self.student.password, "Strong-Password-548!")
        self.assertTrue(self.student.check_password("Strong-Password-548!"))

    def test_superuser_role_defaults_to_admin(self):
        user = User.objects.create_superuser(
            "bootstrap", password="Safe-Bootstrap-Password-328!"
        )
        self.assertEqual(user.role, "ADMIN")

    def test_account_management_password_preservation_and_role_guards(self):
        import json

        admin = User.objects.create_user("admin", role="ADMIN")
        self.client.force_login(admin)
        data = {
            "username": "newfaculty",
            "role": "FACULTY",
            "is_active": True,
            "password": "Strong-Faculty-Password-634!",
        }
        response = self.client.post(
            "/api/accounts/", json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(pk=response.json()["id"])
        self.assertTrue(user.check_password(data["password"]))
        data["password"] = ""
        data["first_name"] = "Teacher"
        self.assertEqual(
            self.client.put(
                f"/api/accounts/{user.pk}/",
                json.dumps(data),
                content_type="application/json",
            ).status_code,
            200,
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("Strong-Faculty-Password-634!"))
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.post(
                "/api/accounts/", json.dumps(data), content_type="application/json"
            ).status_code,
            403,
        )

    def test_password_reset_and_change_pages(self):
        self.student.email = "student@example.edu"
        self.student.save()
        response = self.client.post(
            "/accounts/password_reset/", {"email": self.student.email}
        )
        self.assertEqual(response.status_code, 302)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get("/accounts/password_change/").status_code, 200)
