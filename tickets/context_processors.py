from .permissions import is_employee, is_it_admin, is_it_operator


def role_flags(request):
    """Expose role booleans to all templates, used mainly for navigation."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    return {
        'is_employee_user': is_employee(user),
        'is_it_admin_user': is_it_admin(user),
        'is_it_operator_user': is_it_operator(user),
    }
