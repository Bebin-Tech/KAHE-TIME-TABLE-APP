from .models import DepartmentAccess


def department_ids(user):
    return DepartmentAccess.objects.filter(user=user).values_list(
        "department_id", flat=True
    )


def scoped(queryset, user, department_path):
    if user.is_institution_admin:
        return queryset
    if user.role != "HOD":
        return queryset.none()
    return queryset.filter(**{department_path + "__in": department_ids(user)})
