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
from users.forms import CSVImportForm, UserCreateForm, UserUpdateForm, LieuForm
from tickets.models import UserProfile, Lieu, Service, LieuService
from tickets.permissions import MANAGEABLE_ROLES, can_manage_users, get_user_role, role_required
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import JsonResponse


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
            # Resolve LieuService from selected lieu/service
            lieu = data['lieu']
            service = data['service']
            try:
                lieu_service = LieuService.objects.get(lieu=lieu, service=service, is_active=True)
            except LieuService.DoesNotExist:
                form.add_error('service', "Ce service n'est pas disponible dans ce lieu.")
                return render(request, 'users/user_create.html', {'form': form})

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
                    lieu_service=lieu_service,
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
            # Resolve LieuService
            lieu = data['lieu']
            service = data['service']
            try:
                lieu_service = LieuService.objects.get(lieu=lieu, service=service, is_active=True)
            except LieuService.DoesNotExist:
                form.add_error('service', "Ce service n'est pas disponible dans ce lieu.")
                return render(request, 'users/user_update.html', {'form': form, 'target_user': target_user})

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
                        lieu_service=lieu_service,
                        phone=data.get('phone') or None,
                        is_active=data.get('is_active', True),
                    )
                else:
                    profile.lieu_service = lieu_service
                    profile.phone = data.get('phone') or None
                    profile.is_active = data.get('is_active', True)
                    profile.save()

            messages.success(request, f'User "{target_user.username}" updated successfully.')
            return redirect('user_detail', user_id=target_user.pk)
    else:
        # Prepare initial values for new lieu/service fields
        initial = {
            'first_name': target_user.first_name,
            'last_name': target_user.last_name,
            'email': target_user.email,
            'role': get_user_role(target_user),
            'phone': profile.phone if profile else '',
            'is_active': target_user.is_active,
        }
        if profile and profile.lieu_service:
            initial['lieu'] = profile.lieu_service.lieu_id
            initial['service'] = profile.lieu_service.service_id

        form = UserUpdateForm(
            target_user=target_user,
            initial=initial,
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


# ------------------------------------------------------------------
# Lieu management
# ------------------------------------------------------------------

@login_required
@role_required(can_manage_users)
def lieu_list(request):
    """List lieux with their services."""
    lieux = Lieu.objects.prefetch_related('lieu_services__service').order_by('name')
    return render(request, 'users/lieu_list.html', {'lieux': lieux})


@login_required
@role_required(can_manage_users)
def lieu_create(request):
    """Create a new Lieu and associated LieuService rows for selected services."""
    if request.method == 'POST':
        form = LieuForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                lieu = Lieu.objects.create(
                    name=data['name'],
                    address=data.get('address', '') or None,
                    city=data.get('city', '') or None,
                    description=data.get('description', '') or None,
                    is_active=data.get('is_active', True),
                )
                services = data.get('services') or []
                for svc in services:
                    ls, created = LieuService.objects.get_or_create(lieu=lieu, service=svc)
                    if not ls.is_active:
                        ls.is_active = True
                        ls.save()
            messages.success(request, f'Lieu "{lieu.name}" created successfully.')
            return redirect('lieu_list')
    else:
        form = LieuForm()
    return render(request, 'users/lieu_form.html', {'form': form})


@login_required
@role_required(can_manage_users)
def lieu_edit(request, lieu_id):
    """Edit an existing Lieu and its available services."""
    lieu = get_object_or_404(Lieu, pk=lieu_id)

    if request.method == 'POST':
        form = LieuForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                lieu.name = data['name']
                lieu.address = data.get('address') or None
                lieu.city = data.get('city') or None
                lieu.description = data.get('description') or None
                lieu.is_active = data.get('is_active', True)
                lieu.save()

                selected_services = set(data.get('services') or [])

                # Ensure selected services have LieuService rows (reactivate if needed)
                for svc in selected_services:
                    ls, created = LieuService.objects.get_or_create(lieu=lieu, service=svc)
                    if not ls.is_active:
                        ls.is_active = True
                        ls.save()

                # Deactivate LieuService rows that are no longer selected
                existing_ls = LieuService.objects.filter(lieu=lieu)
                for ls in existing_ls:
                    if ls.service not in selected_services and ls.is_active:
                        ls.is_active = False
                        ls.save()

            messages.success(request, f'Lieu "{lieu.name}" updated successfully.')
            return redirect('lieu_list')
    else:
        initial = {
            'name': lieu.name,
            'address': lieu.address,
            'city': lieu.city,
            'description': lieu.description,
            'is_active': lieu.is_active,
            'services': [ls.service_id for ls in lieu.lieu_services.filter(is_active=True)],
        }
        form = LieuForm(initial=initial)

    return render(request, 'users/lieu_form.html', {'form': form, 'lieu': lieu})


@login_required
@role_required(can_manage_users)
def lieu_delete(request, lieu_id):
    lieu = get_object_or_404(Lieu, pk=lieu_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                lieu.delete()
            messages.success(request, f'Lieu "{lieu.name}" deleted successfully.')
            return redirect('lieu_list')
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                "Ce lieu ne peut pas être supprimé car il est déjà utilisé par des utilisateurs ou des tickets.",
            )
            return redirect('lieu_list')

    return render(request, 'users/lieu_confirm_delete.html', {'lieu': lieu})


@login_required
@role_required(can_manage_users)
def services_by_lieu(request, lieu_id):
    """AJAX endpoint returning JSON list of services for a given lieu."""
    lieu = get_object_or_404(Lieu, pk=lieu_id)
    services = (
        Service.objects.filter(lieu_services__lieu=lieu, lieu_services__is_active=True, is_active=True)
        .distinct()
        .order_by('name')
    )
    data = [{'id': s.pk, 'name': s.name} for s in services]
    return JsonResponse(data, safe=False)
