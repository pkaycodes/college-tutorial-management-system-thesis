from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to users whose .role is in `roles`.

    Backend enforcement of role-based access control (spec section 44) —
    hiding a button in the UI is never sufficient on its own.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("You do not have permission to view this page.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
