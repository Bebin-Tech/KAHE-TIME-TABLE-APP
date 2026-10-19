from academics.models import DepartmentAccess, FacultyProfile, StudentProfile
from .models import Timetable


def visible_timetables(user):
    qs = Timetable.objects.select_related(
        "section__semester__program__department", "section__academic_year"
    )
    if user.is_institution_admin:
        return qs
    if user.role == "HOD":
        return qs.filter(
            section__semester__program__department_id__in=DepartmentAccess.objects.filter(
                user=user
            ).values(
                "department_id"
            )
        )
    qs = qs.filter(status="PUBLISHED")
    if user.role == "FACULTY":
        return qs.filter(entries__faculty__user=user).distinct()
    if user.role == "STUDENT":
        return qs.filter(
            section_id__in=StudentProfile.objects.filter(user=user).values("section_id")
        )
    return qs.none()


def visible_entries(timetable, user):
    qs = timetable.entries.select_related("subject", "faculty__user", "room", "period")
    if user.role == "FACULTY" and not user.is_institution_admin:
        qs = qs.filter(faculty__user=user)
    return qs
