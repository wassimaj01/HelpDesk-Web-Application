from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from .forms import (
    AssignTicketForm,
    ResolveTicketForm,
    TicketCreateForm,
    TicketEditForm,
    ValidateResolutionForm,
)
from .models import Ticket, TicketMessage
from .permissions import is_employee, is_it_admin, is_it_operator, role_required


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """Clean, method-aware logout.

    - POST: actually logs the user out and redirects to the login page.
      This is the only way sessions are ever terminated, and it's what
      the navbar's logout form submits.
    - GET: never crashes and never silently logs anyone out. If the user
      is authenticated they're sent back to their dashboard with a
      reminder to use the Logout button; if they're already logged out
      they're simply sent to the login page.
    """
    if request.method == 'POST':
        if request.user.is_authenticated:
            auth_logout(request)
            messages.success(request, 'You have been logged out successfully.')
        return redirect('login')

    if request.user.is_authenticated:
        messages.info(request, 'Use the Logout button in the navbar to sign out.')
        return redirect('dashboard')
    return redirect('login')


@login_required
def dashboard_redirect(request):
    """Central role-based redirect used right after login and by the navbar.

    - Superusers go straight to the Django admin.
    - IT_Admin members go to their ticket dashboard (tickets routed to them).
    - IT_Operator members go to their assigned-tickets dashboard.
    - Employee members go to their own-tickets dashboard.
    - Anyone else (no role assigned) is sent back to login with an error.
    """
    user = request.user

    if user.is_superuser:
        return redirect('/admin/')
    if is_it_admin(user):
        return redirect('it_admin_dashboard')
    if is_it_operator(user):
        return redirect('operator_dashboard')
    if is_employee(user):
        return redirect('employee_dashboard')

    messages.error(
        request,
        'Your account is not assigned to a role. Please contact your administrator.',
    )
    return redirect('login')


# ----------------------------------------------------------------------
# Employee interface
# ----------------------------------------------------------------------


@login_required
@role_required(is_employee)
def employee_dashboard(request):
    """Employee dashboard: summary stats + list of the employee's own tickets."""
    tickets = (
        Ticket.objects.filter(created_by=request.user)
        .select_related('problem_type', 'responsible_admin', 'assigned_to')
    )

    stats = {
        'total': tickets.count(),
        'created': tickets.filter(status=Ticket.Status.CREATED).count(),
        'assigned': tickets.filter(status=Ticket.Status.ASSIGNED).count(),
        'resolved': tickets.filter(status=Ticket.Status.RESOLVED).count(),
        'closed': tickets.filter(status=Ticket.Status.CLOSED).count(),
        'cancelled': tickets.filter(status=Ticket.Status.CANCELLED).count(),
    }

    context = {
        'tickets': tickets,
        'stats': stats,
        'ticket_status': Ticket.Status,
    }
    return render(request, 'tickets/employee_dashboard.html', context)


@login_required
@role_required(is_employee)
def ticket_create(request):
    """Employee creates a new ticket by choosing a problem type and an
    optional description. category, responsible_admin, status and
    requester_lieu_service are filled automatically.
    """
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        messages.error(
            request,
            'Your account has no location/service profile configured. '
            'Please contact your administrator.',
        )
        return redirect('employee_dashboard')

    if request.method == 'POST':
        form = TicketCreateForm(request.POST)
        if form.is_valid():
            ticket = Ticket.create_for_employee(
                employee=request.user,
                problem_type=form.cleaned_data['problem_type'],
                description=form.cleaned_data.get('description'),
            )
            messages.success(request, f'Ticket {ticket.reference} created successfully.')
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketCreateForm()

    return render(request, 'tickets/ticket_create.html', {'form': form})


@login_required
@role_required(is_employee)
def ticket_detail(request, pk):
    """Employee views the details (and history) of one of their own tickets."""
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'problem_type', 'responsible_admin', 'assigned_to', 'requester_lieu_service'
        ).prefetch_related('history__changed_by'),
        pk=pk,
        created_by=request.user,
    )
    return render(request, 'tickets/ticket_detail.html', {'ticket': ticket})


@login_required
@role_required(is_employee)
def ticket_edit(request, pk):
    """Employee edits the description of their own ticket.

    Only allowed while the ticket status is CREATED. assigned_to,
    status, responsible_admin and category can never be changed here.
    """
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)

    if ticket.status != Ticket.Status.CREATED:
        if request.method == 'POST':
            return HttpResponseForbidden(
                'This ticket can no longer be edited because it is not in CREATED status.'
            )
        messages.error(request, 'Only tickets with status CREATED can be edited.')
        return redirect('ticket_detail', pk=ticket.pk)

    if request.method == 'POST':
        form = TicketEditForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            ticket.update_description(request.user, comment='Description updated by employee.')
            messages.success(request, f'Ticket {ticket.reference} updated successfully.')
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketEditForm(instance=ticket)

    return render(request, 'tickets/ticket_edit.html', {'form': form, 'ticket': ticket})


@login_required
@role_required(is_employee)
def ticket_cancel(request, pk):
    """Employee cancels their own ticket (only allowed while CREATED).

    Cancelling never deletes the ticket; it sets status to CANCELLED.
    """
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)

    if ticket.status != Ticket.Status.CREATED:
        if request.method == 'POST':
            return HttpResponseForbidden(
                'This ticket can no longer be cancelled because it is not in CREATED status.'
            )
        messages.error(request, 'Only tickets with status CREATED can be cancelled.')
        return redirect('ticket_detail', pk=ticket.pk)

    if request.method == 'POST':
        ticket.cancel(request.user, comment=request.POST.get('reason') or None)
        messages.success(request, f'Ticket {ticket.reference} has been cancelled.')
        return redirect('employee_dashboard')

    return redirect('ticket_detail', pk=ticket.pk)


# ----------------------------------------------------------------------
# IT Admin interface
# ----------------------------------------------------------------------


def _active_operators():
    return User.objects.filter(groups__name='IT_Operator', is_active=True).order_by('username')


@login_required
@role_required(is_it_admin)
def it_admin_dashboard(request):
    """IT admin dashboard: tickets routed to this admin only."""
    tickets = Ticket.objects.filter(responsible_admin=request.user).select_related(
        'problem_type', 'created_by', 'assigned_to'
    )

    stats = {
        'total': tickets.count(),
        'created': tickets.filter(status=Ticket.Status.CREATED).count(),
        'assigned': tickets.filter(status=Ticket.Status.ASSIGNED).count(),
        'resolved': tickets.filter(status=Ticket.Status.RESOLVED).count(),
        'closed': tickets.filter(status=Ticket.Status.CLOSED).count(),
    }

    context = {'tickets': tickets, 'stats': stats}
    return render(request, 'tickets/it_admin_dashboard.html', context)


@login_required
@role_required(is_it_admin)
def it_admin_ticket_detail(request, ticket_id):
    """IT admin views a ticket, but only if it was routed to them."""
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'problem_type', 'created_by', 'assigned_to', 'requester_lieu_service'
        ).prefetch_related('history__changed_by'),
        id=ticket_id,
        responsible_admin=request.user,
    )
    return render(request, 'tickets/it_admin_ticket_detail.html', {'ticket': ticket})


@login_required
@role_required(is_it_admin)
def it_admin_assign_ticket(request, ticket_id):
    """IT admin assigns a CREATED ticket, or reassigns an ASSIGNED ticket."""
    ticket = get_object_or_404(Ticket, id=ticket_id, responsible_admin=request.user)

    if ticket.status not in (Ticket.Status.CREATED, Ticket.Status.ASSIGNED):
        if request.method == 'POST':
            return HttpResponseForbidden('This ticket cannot be assigned in its current status.')
        messages.error(request, 'This ticket cannot be assigned in its current status.')
        return redirect('it_admin_ticket_detail', ticket_id=ticket.pk)

    operators = _active_operators()

    if request.method == 'POST':
        form = AssignTicketForm(request.POST, operators=operators)
        if form.is_valid():
            operator = form.cleaned_data['operator']
            ticket.assign_to_operator(
                operator, request.user, comment=form.cleaned_data.get('comment') or None
            )
            messages.success(
                request, f'Ticket {ticket.reference} assigned to {operator.get_username()}.'
            )
            return redirect('it_admin_ticket_detail', ticket_id=ticket.pk)
    else:
        form = AssignTicketForm(operators=operators, initial={'operator': ticket.assigned_to_id})

    return render(
        request, 'tickets/it_admin_assign_ticket.html', {'form': form, 'ticket': ticket}
    )


@login_required
@role_required(is_it_admin)
def it_admin_validate_resolution(request, ticket_id):
    """IT admin accepts or refuses a RESOLVED ticket."""
    ticket = get_object_or_404(Ticket, id=ticket_id, responsible_admin=request.user)

    if ticket.status != Ticket.Status.RESOLVED:
        if request.method == 'POST':
            return HttpResponseForbidden(
                'Only resolved tickets pending validation can be processed here.'
            )
        messages.error(request, 'Only resolved tickets pending validation can be processed here.')
        return redirect('it_admin_ticket_detail', ticket_id=ticket.pk)

    operators = _active_operators()

    if request.method == 'POST':
        form = ValidateResolutionForm(request.POST, operators=operators)
        if form.is_valid():
            comment = form.cleaned_data.get('comment') or None
            if form.cleaned_data['decision'] == ValidateResolutionForm.ACCEPT:
                ticket.accept_resolution(request.user, comment=comment)
                messages.success(
                    request, f'Resolution for {ticket.reference} accepted. Ticket closed.'
                )
            else:
                operator = form.cleaned_data['operator']
                ticket.refuse_resolution(request.user, operator, comment=comment)
                messages.warning(
                    request,
                    f'Resolution for {ticket.reference} refused and reassigned to '
                    f'{operator.get_username()}.',
                )
            return redirect('it_admin_ticket_detail', ticket_id=ticket.pk)
    else:
        form = ValidateResolutionForm(
            operators=operators, initial={'operator': ticket.assigned_to_id}
        )

    return render(
        request, 'tickets/it_admin_validate_resolution.html', {'form': form, 'ticket': ticket}
    )


# New: IT Admin hard delete ticket
@login_required
@role_required(is_it_admin)
def it_admin_delete_ticket(request, ticket_id):
    """Hard-delete a ticket routed to this admin. Only allowed for responsible admin."""
    ticket = get_object_or_404(Ticket, id=ticket_id, responsible_admin=request.user)

    if request.method == 'POST':
        ref = ticket.reference
        ticket.delete()
        messages.success(request, f'Ticket {ref} has been permanently deleted.')
        return redirect('it_admin_dashboard')

    # GET -> show confirmation
    return render(request, 'tickets/it_admin_delete_ticket.html', {'ticket': ticket})


# ----------------------------------------------------------------------
# IT Operator interface
# ----------------------------------------------------------------------


@login_required
@role_required(is_it_operator)
def operator_dashboard(request):
    """IT operator dashboard: tickets assigned to this operator only."""
    tickets = Ticket.objects.filter(assigned_to=request.user).select_related(
        'problem_type', 'created_by', 'responsible_admin'
    )

    stats = {
        'total': tickets.count(),
        'assigned': tickets.filter(status=Ticket.Status.ASSIGNED).count(),
        'resolved': tickets.filter(status=Ticket.Status.RESOLVED).count(),
        'closed': tickets.filter(status=Ticket.Status.CLOSED).count(),
    }

    context = {'tickets': tickets, 'stats': stats}
    return render(request, 'tickets/operator_dashboard.html', context)


@login_required
@role_required(is_it_operator)
def operator_ticket_detail(request, ticket_id):
    """IT operator views a ticket, but only if it is assigned to them."""
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'problem_type', 'created_by', 'responsible_admin', 'requester_lieu_service'
        ).prefetch_related('history__changed_by'),
        id=ticket_id,
        assigned_to=request.user,
    )
    return render(request, 'tickets/operator_ticket_detail.html', {'ticket': ticket})


@login_required
@role_required(is_it_operator)
def operator_mark_resolved(request, ticket_id):
    """IT operator marks an ASSIGNED ticket (assigned to them) as resolved."""
    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if ticket.status != Ticket.Status.ASSIGNED:
        if request.method == 'POST':
            return HttpResponseForbidden('This ticket cannot be resolved in its current status.')
        messages.error(request, 'Only assigned tickets can be marked as resolved.')
        return redirect('operator_ticket_detail', ticket_id=ticket.pk)

    if request.method == 'POST':
        form = ResolveTicketForm(request.POST)
        if form.is_valid():
            ticket.mark_as_resolved(request.user, comment=form.cleaned_data.get('comment') or None)
            messages.success(request, f'Ticket {ticket.reference} marked as resolved.')
            return redirect('operator_ticket_detail', ticket_id=ticket.pk)
    else:
        form = ResolveTicketForm()

    return render(
        request, 'tickets/operator_mark_resolved.html', {'form': form, 'ticket': ticket}
    )


# New: Operator return ticket
@login_required
@role_required(is_it_operator)
def operator_return_ticket(request, ticket_id):
    """Operator returns an ASSIGNED ticket back to CREATED if they cannot handle it.

    Rules enforced:
    - only assigned operator (assigned_to == request.user)
    - only when ticket.status == ASSIGNED
    - POST required to perform the action; GET displays a confirmation form
    """
    ticket = get_object_or_404(Ticket, id=ticket_id, assigned_to=request.user)

    if ticket.status != Ticket.Status.ASSIGNED:
        if request.method == 'POST':
            return HttpResponseForbidden('This ticket cannot be returned in its current status.')
        messages.error(request, 'Only assigned tickets can be returned.')
        return redirect('operator_ticket_detail', ticket_id=ticket.pk)

    if request.method == 'POST':
        reason = (request.POST.get('reason') or '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for returning the ticket.')
            return render(request, 'tickets/operator_return_ticket.html', {'ticket': ticket})

        old_assigned = ticket.assigned_to

        ticket.status = Ticket.Status.CREATED
        ticket.assigned_to = None
        ticket.assigned_by = None
        ticket.assigned_at = None
        ticket.resolved_by = None
        ticket.resolved_at = None
        ticket.admin_validation_decision = None
        ticket.save()

        # create history entry
        from .models import TicketHistory

        TicketHistory.objects.create(
            ticket=ticket,
            action=TicketHistory.Action.OPERATOR_RETURNED,
            old_status=Ticket.Status.ASSIGNED,
            new_status=Ticket.Status.CREATED,
            old_assigned_to=old_assigned,
            new_assigned_to=None,
            changed_by=request.user,
            comment=reason,
        )

        messages.success(request, f'Ticket {ticket.reference} has been returned for reassignment.')
        return redirect('operator_dashboard')

    return render(request, 'tickets/operator_return_ticket.html', {'ticket': ticket})


# ----------------------------------------------------------------------
# Ticket discussion (AJAX endpoints)
# ----------------------------------------------------------------------


@login_required
@require_GET
def ticket_messages(request, ticket_id):
    """Return JSON list of messages for a ticket.

    Only the ticket creator (employee) and the responsible admin can access.
    Operators are not allowed.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Permission check: only created_by or responsible_admin
    if not (request.user.pk == ticket.created_by_id or request.user.pk == ticket.responsible_admin_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    messages_qs = ticket.messages.select_related('sender').order_by('created_at')
    data = []
    for m in messages_qs:
        data.append(
            {
                'id': m.id,
                'sender': m.sender.get_username(),
                'message': m.message,
                'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
            }
        )
    return JsonResponse({'messages': data})


@login_required
@require_POST
def ticket_send_message(request, ticket_id):
    """Accept a new message for the ticket via POST (message=...).

    Security rules same as ticket_messages.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if not (request.user.pk == ticket.created_by_id or request.user.pk == ticket.responsible_admin_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    text = (request.POST.get('message') or '').strip()
    if not text:
        return JsonResponse({'error': 'Empty message'}, status=400)

    msg = TicketMessage.objects.create(ticket=ticket, sender=request.user, message=text)

    # Return the created message
    data = {
        'id': msg.id,
        'sender': msg.sender.get_username(),
        'message': msg.message,
        'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
    }
    return JsonResponse({'success': True, 'message': data})

