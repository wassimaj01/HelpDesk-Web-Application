"""User management views (moved from tickets.user_views).

This module intentionally imports UserProfile and other models from the
`tickets` app (UserProfile remains defined there to avoid migration churn).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from tickets.csv_import import import_users_from_csv
from users.forms import CSVImportForm, UserCreateForm, UserUpdateForm
from tickets.models import UserProfile
from tickets.permissions import MANAGEABLE_ROLES, can_manage_users, get_user_role, role_required


def _users_queryset():
    return (
        User.objects.select_related('profile__lieu_service__lieu', 'profile__lieu_service__service')
        .prefetch_related('groups')
        .order_by('username')
    )


@login_required
@role_required(can_manage_users)
def user_management_dashboard(request):
    """List every application user with role, location/service and status."""
    users = _users_queryset()

    stats = {
        'total': users.count(),
        'employees': users.filter(groups__name='Employee').count(),
        'it_admins': users.filter(groups__name='IT_Admin').count(),
        'it_operators': users.filter(groups__name='IT_Operator').count(),
        'active': users.filter(is_active=True).count(),
        'inactive': users.filter(is_active=False).count(),
    }

    # Attach a display-friendly role label to each user without an extra query.
    for target_user in users:
        target_user.role_label = get_user_role(target_user)

    context = {'users': users, 'stats': stats}
    return render(request, 'users/user_management_dashboard.html', context)


@login_required
@role_required(can_manage_users)
def user_create(request):
    """Manually create a new Employee / IT_Admin / IT_Operator user."""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                new_user = User.objects.create(
                    username=data['username'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                    email=data.get('email', ''),
                    is_active=data.get('is_active', True),
                    # Always forced, regardless of role: this interface
                    # must never create staff or superuser accounts.
                    is_staff=False,
                    is_superuser=False,
                )
                new_user.set_password(data['password'])
                new_user.save()

                group = Group.objects.get(name=data['role'])
                new_user.groups.add(group)

                UserProfile.objects.create(
                    user=new_user,
                    lieu_service=data['lieu_service'],
                    phone=data.get('phone') or None,
                    is_active=data.get('is_active', True),
                )
            messages.success(request, f'User "{new_user.username}" created successfully.')
            return redirect('user_detail', user_id=new_user.pk)
    else:
        form = UserCreateForm()

    return render(request, 'users/user_create.html', {'form': form})


@login_required
@role_required(can_manage_users)
def user_detail(request, user_id):
    """Read-only detail view of a single user."""
    target_user = get_object_or_404(
        User.objects.select_related('profile__lieu_service__lieu', 'profile__lieu_service__service')
        .prefetch_related('groups'),
        pk=user_id,
    )
    context = {
        'target_user': target_user,
        'role_label': get_user_role(target_user),
        'profile': getattr(target_user, 'profile', None),
    }
    return render(request, 'users/user_detail.html', context)


@login_required
@role_required(can_manage_users)
def user_update(request, user_id):
    """Edit an existing user's profile information and role."""
    target_user = get_object_or_404(User, pk=user_id)

    if target_user.is_superuser:
        messages.error(request, 'Superuser accounts must be managed from the Django admin.')
        return redirect('user_management_dashboard')

    profile = getattr(target_user, 'profile', None)

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, target_user=target_user)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                target_user.first_name = data.get('first_name', '')
                target_user.last_name = data.get('last_name', '')
                target_user.email = data.get('email', '')
                target_user.is_active = data.get('is_active', True)
                target_user.save()

                # Reset manageable-role groups, then assign the selected one.
                target_user.groups.remove(*Group.objects.filter(name__in=MANAGEABLE_ROLES))
                new_group = Group.objects.get(name=data['role'])
                target_user.groups.add(new_group)

                if profile is None:
                    UserProfile.objects.create(
                        user=target_user,
                        lieu_service=data['lieu_service'],
                        phone=data.get('phone') or None,
                        is_active=data.get('is_active', True),
                    )
                else:
                    profile.lieu_service = data['lieu_service']
                    profile.phone = data.get('phone') or None
                    profile.is_active = data.get('is_active', True)
                    profile.save()

            messages.success(request, f'User "{target_user.username}" updated successfully.')
            return redirect('user_detail', user_id=target_user.pk)
    else:
        form = UserUpdateForm(
            target_user=target_user,
            initial={
                'first_name': target_user.first_name,
                'last_name': target_user.last_name,
                'email': target_user.email,
                'role': get_user_role(target_user),
                'lieu_service': profile.lieu_service_id if profile else None,
                'phone': profile.phone if profile else '',
                'is_active': target_user.is_active,
            },
        )

    return render(request, 'users/user_update.html', {'form': form, 'target_user': target_user})


@login_required
@role_required(can_manage_users)
def user_deactivate(request, user_id):
    """Deactivate (or reactivate) a user without ever deleting them.

    Toggling both User.is_active and UserProfile.is_active keeps the two
    in sync. Superuser accounts are excluded; they're managed in the
    Django admin only.
    """
    target_user = get_object_or_404(User, pk=user_id)

    if target_user.is_superuser:
        messages.error(request, 'Superuser accounts must be managed from the Django admin.')
        return redirect('user_management_dashboard')

    if request.method == 'POST':
        with transaction.atomic():
            target_user.is_active = not target_user.is_active
            target_user.save()
            profile = getattr(target_user, 'profile', None)
            if profile is not None:
                profile.is_active = target_user.is_active
                profile.save()

        if target_user.is_active:
            messages.success(request, f'User "{target_user.username}" has been reactivated.')
        else:
            messages.success(request, f'User "{target_user.username}" has been deactivated.')
        return redirect('user_management_dashboard')

    return redirect('user_detail', user_id=target_user.pk)


@login_required
@role_required(can_manage_users)
def user_import_csv(request):
    """Upload a CSV file to bulk-create users."""
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            results = import_users_from_csv(form.cleaned_data['csv_file'])
            if results['fatal_error']:
                messages.error(request, results['fatal_error'])
            else:
                messages.success(
                    request,
                    f"{results['created_count']} user(s) created, "
                    f"{results['skipped_count']} row(s) skipped.",
                )
            return render(request, 'users/import_result.html', {'results': results})
    else:
        form = CSVImportForm()

    return render(request, 'users/user_import_csv.html', {'form': form})
