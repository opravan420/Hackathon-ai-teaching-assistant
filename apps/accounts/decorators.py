from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

def role_required(*roles):
    """
    Decorator for views that checks whether a user has the appropriate role.
    Redirects to login if not authenticated.
    Raises PermissionDenied if authenticated but unauthorized.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view
    return decorator
