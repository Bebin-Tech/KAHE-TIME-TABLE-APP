from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CollegeUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "ADMIN")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    objects = CollegeUserManager()

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        HOD = "HOD", "Head of department"
        FACULTY = "FACULTY", "Faculty"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    @property
    def is_institution_admin(self):
        return self.is_active and (self.is_superuser or self.role == self.Role.ADMIN)
