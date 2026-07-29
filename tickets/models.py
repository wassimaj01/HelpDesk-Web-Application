from django.conf import settings
from django.db import models
from django.utils import timezone


class Lieu(models.Model):
    """A physical location/site of the organization."""

    name = models.CharField(max_length=150)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Service(models.Model):
    """A work department/service (e.g. Adhesion, Liquidation, Informatique)."""

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class LieuService(models.Model):
    """Association between a Lieu and a Service it hosts."""

    lieu = models.ForeignKey(Lieu, on_delete=models.CASCADE, related_name='lieu_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='lieu_services')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('lieu', 'service')
        ordering = ['lieu__name', 'service__name']

    def __str__(self):
        return f'{self.lieu} - {self.service}'


class UserProfile(models.Model):
    """Professional information attached to a Django User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    lieu_service = models.ForeignKey(
        LieuService, on_delete=models.PROTECT, related_name='user_profiles'
    )
    phone = models.CharField(max_length=30, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_username()} profile'


class ProblemType(models.Model):
    """Predefined problem an employee can select when creating a ticket."""

    class Category(models.TextChoices):
        NETWORK_TELECOM_HELPDESK = 'NETWORK_TELECOM_HELPDESK', 'Network / Telecom / Helpdesk'
        APPLICATION_DATABASE_SOFTWARE = (
            'APPLICATION_DATABASE_SOFTWARE', 'Application / Database / Software'
        )

    label = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=40, choices=Category.choices)
    responsible_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_problem_types',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label


class Ticket(models.Model):
    """Central model representing an IT support ticket."""

    class Status(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class ValidationDecision(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REFUSED = 'REFUSED', 'Refused'
    
    """reference a generer automatiquement"""
    reference = models.CharField(max_length=50, unique=True) 
    problem_type = models.ForeignKey(
        ProblemType, on_delete=models.PROTECT, related_name='tickets'
    )
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=40, choices=ProblemType.Category.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_tickets'
    )
    requester_lieu_service = models.ForeignKey(
        LieuService, on_delete=models.PROTECT, related_name='requested_tickets'
    )
    responsible_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='admin_tickets'
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_tickets',
        blank=True,
        null=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='tickets_assigned_by_me',
        blank=True,
        null=True,
    )
    assigned_at = models.DateTimeField(blank=True, null=True)

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='resolved_tickets',
        blank=True,
        null=True,
    )
    resolved_at = models.DateTimeField(blank=True, null=True)

    admin_validation_decision = models.CharField(
        max_length=20, choices=ValidationDecision.choices, blank=True, null=True
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='validated_tickets',
        blank=True,
        null=True,
    )
    validated_at = models.DateTimeField(blank=True, null=True)

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_tickets',
        blank=True,
        null=True,
    )
    closed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    # ------------------------------------------------------------------
    # Business methods / workflow transitions
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_reference():
        """Generate a unique, human-readable ticket reference (e.g. TCK-9F3A2B1C4D)."""
        import uuid

        return f'TCK-{uuid.uuid4().hex[:10].upper()}'

    @classmethod
    def create_for_employee(cls, employee, problem_type, description=None):
        """Create a ticket on behalf of an employee.

        category and responsible_admin are derived from problem_type.
        requester_lieu_service is derived from the employee's profile.
        Creates TICKET_CREATED and TICKET_ROUTED history entries.
        """
        profile = getattr(employee, 'profile', None)
        if profile is None:
            raise ValueError('The employee has no associated profile / lieu_service.')

        reference = cls._generate_reference()
        while cls.objects.filter(reference=reference).exists():
            reference = cls._generate_reference()

        ticket = cls.objects.create(
            reference=reference,
            problem_type=problem_type,
            description=description,
            category=problem_type.category,
            status=cls.Status.CREATED,
            created_by=employee,
            requester_lieu_service=profile.lieu_service,
            responsible_admin=problem_type.responsible_admin,
        )

        TicketHistory.objects.create(
            ticket=ticket,
            action=TicketHistory.Action.TICKET_CREATED,
            new_status=ticket.status,
            changed_by=employee,
        )
        TicketHistory.objects.create(
            ticket=ticket,
            action=TicketHistory.Action.TICKET_ROUTED,
            old_status=ticket.status,
            new_status=ticket.status,
            new_assigned_to=None,
            changed_by=employee,
            comment=(
                f'Routed to {problem_type.responsible_admin} based on problem type '
                f'"{problem_type.label}".'
            ),
        )
        return ticket

    def update_description(self, employee, comment=None):
        """Record a TICKET_UPDATED history entry after the employee edits a
        CREATED ticket's description. The caller is responsible for saving
        the updated field(s) beforehand.
        """
        if employee.pk != self.created_by_id:
            raise PermissionError('Only the ticket creator can update this ticket.')

        if self.status != self.Status.CREATED:
            raise ValueError(f'Cannot update ticket from status {self.status}.')

        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.TICKET_UPDATED,
            old_status=self.status,
            new_status=self.status,
            changed_by=employee,
            comment=comment,
        )
        return self

    def cancel(self, employee, comment=None):
        """Employee cancels their own ticket. Only valid from CREATED status.

        Cancelling never deletes the ticket; it moves status to CANCELLED.
        """
        if employee.pk != self.created_by_id:
            raise PermissionError('Only the ticket creator can cancel this ticket.')

        if self.status != self.Status.CREATED:
            raise ValueError(f'Cannot cancel ticket from status {self.status}.')

        old_status = self.status
        self.status = self.Status.CANCELLED
        self.save()

        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.TICKET_CANCELLED,
            old_status=old_status,
            new_status=self.status,
            changed_by=employee,
            comment=comment,
        )
        return self

    def assign_to_operator(self, operator, admin_user, comment=None):
        """Responsible admin assigns (or reassigns) the ticket to an operator.

        Valid from CREATED or RESOLVED (RESOLVED->ASSIGNED is handled by
        refuse_resolution, but this method also supports a direct
        CREATED -> ASSIGNED transition).
        """
        if admin_user.pk != self.responsible_admin_id:
            raise PermissionError('Only the responsible admin can assign this ticket.')

        if self.status not in (self.Status.CREATED, self.Status.ASSIGNED):
            raise ValueError(
                f'Cannot assign ticket from status {self.status}.'
            )

        old_status = self.status
        is_reassignment = self.status == self.Status.ASSIGNED

        self.status = self.Status.ASSIGNED
        self.assigned_to = operator
        self.assigned_by = admin_user
        self.assigned_at = timezone.now()
        self.save()

        TicketHistory.objects.create(
            ticket=self,
            action=(
                TicketHistory.Action.TICKET_REASSIGNED
                if is_reassignment
                else TicketHistory.Action.TICKET_ASSIGNED
            ),
            old_status=old_status,
            new_status=self.status,
            new_assigned_to=operator,
            changed_by=admin_user,
            comment=comment,
        )
        return self

    def mark_as_resolved(self, operator_user, comment=None):
        """Assigned operator marks the ticket as resolved."""
        if operator_user.pk != self.assigned_to_id:
            raise PermissionError('Only the assigned operator can resolve this ticket.')

        if self.status != self.Status.ASSIGNED:
            raise ValueError(f'Cannot resolve ticket from status {self.status}.')

        old_status = self.status
        self.status = self.Status.RESOLVED
        self.resolved_by = operator_user
        self.resolved_at = timezone.now()
        self.admin_validation_decision = self.ValidationDecision.PENDING
        self.save()

        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.TICKET_RESOLVED,
            old_status=old_status,
            new_status=self.status,
            changed_by=operator_user,
            comment=comment,
        )
        return self

    def accept_resolution(self, admin_user, comment=None):
        """Responsible admin accepts the resolution and closes the ticket."""
        if admin_user.pk != self.responsible_admin_id:
            raise PermissionError('Only the responsible admin can validate this ticket.')

        if self.status != self.Status.RESOLVED:
            raise ValueError(f'Cannot accept resolution from status {self.status}.')

        now = timezone.now()
        old_status = self.status

        self.admin_validation_decision = self.ValidationDecision.ACCEPTED
        self.validated_by = admin_user
        self.validated_at = now
        self.status = self.Status.CLOSED
        self.closed_by = admin_user
        self.closed_at = now
        self.save()

        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.RESOLUTION_ACCEPTED,
            old_status=old_status,
            new_status=self.status,
            changed_by=admin_user,
            comment=comment,
        )
        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.TICKET_CLOSED,
            old_status=old_status,
            new_status=self.status,
            changed_by=admin_user,
            comment=comment,
        )
        return self

    def refuse_resolution(self, admin_user, operator, comment=None):
        """Responsible admin refuses the resolution and reassigns the ticket."""
        if admin_user.pk != self.responsible_admin_id:
            raise PermissionError('Only the responsible admin can validate this ticket.')

        if self.status != self.Status.RESOLVED:
            raise ValueError(f'Cannot refuse resolution from status {self.status}.')

        old_status = self.status
        old_assigned_to = self.assigned_to
        now = timezone.now()

        self.admin_validation_decision = self.ValidationDecision.REFUSED
        self.validated_by = admin_user
        self.validated_at = now
        self.status = self.Status.ASSIGNED
        self.assigned_to = operator
        self.assigned_by = admin_user
        self.assigned_at = now
        self.save()

        TicketHistory.objects.create(
            ticket=self,
            action=TicketHistory.Action.RESOLUTION_REFUSED,
            old_status=old_status,
            new_status=self.status,
            old_assigned_to=old_assigned_to,
            new_assigned_to=operator,
            changed_by=admin_user,
            comment=comment,
        )
        return self


class TicketHistory(models.Model):
    """Traceability record for every important action performed on a ticket."""

    class Action(models.TextChoices):
        TICKET_CREATED = 'TICKET_CREATED', 'Ticket created'
        TICKET_ROUTED = 'TICKET_ROUTED', 'Ticket routed'
        TICKET_UPDATED = 'TICKET_UPDATED', 'Ticket updated'
        TICKET_ASSIGNED = 'TICKET_ASSIGNED', 'Ticket assigned'
        TICKET_REASSIGNED = 'TICKET_REASSIGNED', 'Ticket reassigned'
        TICKET_RESOLVED = 'TICKET_RESOLVED', 'Ticket resolved'
        RESOLUTION_ACCEPTED = 'RESOLUTION_ACCEPTED', 'Resolution accepted'
        RESOLUTION_REFUSED = 'RESOLUTION_REFUSED', 'Resolution refused'
        TICKET_CLOSED = 'TICKET_CLOSED', 'Ticket closed'
        TICKET_CANCELLED = 'TICKET_CANCELLED', 'Ticket cancelled'
        COMMENT_ADDED = 'COMMENT_ADDED', 'Comment added'
        OPERATOR_RETURNED = 'OPERATOR_RETURNED', 'Operator returned'

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=30, choices=Action.choices)
    old_status = models.CharField(
        max_length=20, choices=Ticket.Status.choices, blank=True, null=True
    )
    new_status = models.CharField(
        max_length=20, choices=Ticket.Status.choices, blank=True, null=True
    )
    old_assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='old_ticket_assignments',
        blank=True,
        null=True,
    )
    new_assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='new_ticket_assignments',
        blank=True,
        null=True,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ticket_history_actions'
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'Ticket histories'

    def __str__(self):
        return f'{self.ticket.reference} - {self.action}'


class TicketMessage(models.Model):
    """A message exchanged between the ticket creator (employee) and the responsible admin.

    Operators must NOT access these messages.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ticket_messages')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message #{self.pk} on {self.ticket.reference} by {self.sender.get_username()}'
