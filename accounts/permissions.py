from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def roles_required(*roles):
    def decorate(view):
        @login_required
        @wraps(view)
        def protected(request, *args, **kwargs):
            if not request.user.is_institution_admin and request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return protected

    return decorate
