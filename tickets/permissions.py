"""Role/permission helpers shared by employee, IT admin and IT operator views.

Roles are represented by Django Groups (Employee, IT_Admin, IT_Operator,
Super_Admin) as configured by tickets/management/commands/seed_demo_data.py.
"""

from functools import wraps

from django.http import HttpResponseForbidden


def user_in_group(user, group_name):
    """Return True if the (authenticated) user belongs to the given group."""
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def is_it_admin(user):
    return user_in_group(user, 'IT_Admin')


def is_it_operator(user):
    return user_in_group(user, 'IT_Operator')


def is_employee(user):
    return user_in_group(user, 'Employee')


# Roles that the custom user-management interface is allowed to assign.
# Super_Admin is intentionally excluded: superuser accounts must always be
# created/managed through the Django admin, never through this interface.
MANAGEABLE_ROLES = ['Employee', 'IT_Admin', 'IT_Operator']


def can_manage_users(user):
    """True for superusers and members of the IT_Admin group.

    This is the single gate used by every view in the user-management
    interface (dashboard, create, detail, update, deactivate, CSV import).
    """
    return user.is_authenticated and (user.is_superuser or is_it_admin(user))


def get_user_role(user):
    """Best-effort single role label for display purposes.

    Superusers are always reported as Super_Admin regardless of their
    group memberships. Otherwise the first manageable-role group the
    user belongs to is returned, or None if the user has no role group.
    """
    if user.is_superuser:
        return 'Super_Admin'
    group = user.groups.filter(name__in=MANAGEABLE_ROLES).first()
    return group.name if group else None


def role_required(check_func):
    """View decorator: return HttpResponseForbidden if check_func(user) is False.

    Must be combined with @login_required (placed above this decorator) so
    that anonymous users are redirected to the login page instead of
    receiving a 403.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not check_func(request.user):
                return HttpResponseForbidden(
                    'You do not have permission to access this page.'
                )
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
