from django import forms
from django.contrib.auth.models import User

from .models import LieuService, ProblemType, Ticket
from .permissions import MANAGEABLE_ROLES


class TicketCreateForm(forms.ModelForm):
    """Form used by an employee to create a ticket.

    Only problem_type and description are exposed. category,
    responsible_admin, requester_lieu_service and status are filled
    automatically by Ticket.create_for_employee().
    """

    problem_type = forms.ModelChoiceField(
        queryset=ProblemType.objects.filter(is_active=True),
        label='Problem type',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Ticket
        fields = ['problem_type', 'description']
        widgets = {
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Optional description of the problem...',
                }
            ),
        }
        labels = {
            'description': 'Description (optional)',
        }


class TicketEditForm(forms.ModelForm):
    """Form used by an employee to edit their own ticket.

    Only the description can be modified. assigned_to, status,
    responsible_admin and category are never exposed here.
    """

    class Meta:
        model = Ticket
        fields = ['description']
        widgets = {
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Optional description of the problem...',
                }
            ),
        }
        labels = {
            'description': 'Description (optional)',
        }


class AssignTicketForm(forms.Form):
    """Used by an IT admin to assign or reassign a ticket to an operator."""

    operator = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Operator',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comment = forms.CharField(
        required=False,
        label='Comment (optional)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, operators=None, **kwargs):
        super().__init__(*args, **kwargs)
        if operators is not None:
            self.fields['operator'].queryset = operators


class ValidateResolutionForm(forms.Form):
    """Used by an IT admin to accept or refuse a resolved ticket."""

    ACCEPT = 'ACCEPT'
    REFUSE = 'REFUSE'
    DECISION_CHOICES = [
        (ACCEPT, 'Accept resolution and close the ticket'),
        (REFUSE, 'Refuse resolution and reassign the ticket'),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect,
        label='Decision',
    )
    operator = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Reassign to operator (required if refusing)',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comment = forms.CharField(
        required=False,
        label='Comment',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, operators=None, **kwargs):
        super().__init__(*args, **kwargs)
        if operators is not None:
            self.fields['operator'].queryset = operators

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('decision') == self.REFUSE and not cleaned_data.get('operator'):
            self.add_error('operator', 'Select an operator to reassign this ticket to.')
        return cleaned_data


class ResolveTicketForm(forms.Form):
    """Used by an IT operator to mark an assigned ticket as resolved."""

    comment = forms.CharField(
        required=False,
        label='Resolution comment (optional)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
    )


