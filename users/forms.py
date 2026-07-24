from django import forms
from django.contrib.auth.models import User

from tickets.models import LieuService, Lieu, Service
from tickets.permissions import MANAGEABLE_ROLES


ROLE_CHOICES = [(name, name.replace('_', ' ')) for name in MANAGEABLE_ROLES]


def _active_lieu_services():
    return (
        LieuService.objects.select_related('lieu', 'service')
        .filter(is_active=True)
        .order_by('lieu__name', 'service__name')
    )


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    # New separate lieu and service fields
    lieu = forms.ModelChoiceField(queryset=Lieu.objects.filter(is_active=True).order_by('name'), label='Lieu', widget=forms.Select(attrs={'class': 'form-select'}))
    service = forms.ModelChoiceField(queryset=Service.objects.none(), label='Service', widget=forms.Select(attrs={'class': 'form-select'}))

    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active = forms.BooleanField(required=False, initial=True, label='Active', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine selected lieu from bound data (POST) or initial value
        data = kwargs.get('data') if 'data' in kwargs else (args[0] if len(args) > 0 else None)
        selected_lieu_id = None
        if data:
            try:
                selected_lieu_id = data.get('lieu')
            except Exception:
                selected_lieu_id = None
        if not selected_lieu_id and 'initial' in kwargs:
            selected_lieu_id = kwargs['initial'].get('lieu')

        if selected_lieu_id:
            # Populate services that are active and available in the selected lieu
            self.fields['service'].queryset = (
                Service.objects.filter(
                    lieu_services__lieu_id=selected_lieu_id,
                    lieu_services__is_active=True,
                    is_active=True,
                )
                .distinct()
                .order_by('name')
            )
        else:
            self.fields['service'].queryset = Service.objects.none()

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        # Validate lieu/service pair
        lieu = cleaned_data.get('lieu')
        service = cleaned_data.get('service')
        if not lieu:
            self.add_error('lieu', 'Lieu is required.')
        if not service:
            self.add_error('service', 'Service is required.')
        if lieu and service:
            exists = LieuService.objects.filter(lieu=lieu, service=service, is_active=True).exists()
            if not exists:
                self.add_error('service', 'Ce service n\'est pas disponible dans ce lieu.')
        return cleaned_data


class UserUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    lieu = forms.ModelChoiceField(queryset=Lieu.objects.filter(is_active=True).order_by('name'), label='Lieu', widget=forms.Select(attrs={'class': 'form-select'}))
    service = forms.ModelChoiceField(queryset=Service.objects.none(), label='Service', widget=forms.Select(attrs={'class': 'form-select'}))

    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active = forms.BooleanField(required=False, label='Active', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, target_user=None, **kwargs):
        self.target_user = target_user
        super().__init__(*args, **kwargs)
        # Determine selected lieu from bound data (POST) or initial value
        data = kwargs.get('data') if 'data' in kwargs else (args[0] if len(args) > 0 else None)
        selected_lieu_id = None
        if data:
            try:
                selected_lieu_id = data.get('lieu')
            except Exception:
                selected_lieu_id = None
        if not selected_lieu_id and 'initial' in kwargs:
            selected_lieu_id = kwargs['initial'].get('lieu')

        if selected_lieu_id:
            self.fields['service'].queryset = (
                Service.objects.filter(
                    lieu_services__lieu_id=selected_lieu_id,
                    lieu_services__is_active=True,
                    is_active=True,
                )
                .distinct()
                .order_by('name')
            )
        else:
            # Fallback to the user's current service if present (when editing)
            if self.target_user is not None:
                profile = getattr(self.target_user, 'profile', None)
                if profile is not None and profile.lieu_service is not None:
                    self.fields['service'].queryset = Service.objects.filter(pk=profile.lieu_service.service_id)
                else:
                    self.fields['service'].queryset = Service.objects.none()
            else:
                self.fields['service'].queryset = Service.objects.none()

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and self.target_user is not None:
            clash = User.objects.filter(email__iexact=email).exclude(pk=self.target_user.pk)
            if clash.exists():
                raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        lieu = cleaned_data.get('lieu')
        service = cleaned_data.get('service')
        if not lieu:
            self.add_error('lieu', 'Lieu is required.')
        if not service:
            self.add_error('service', 'Service is required.')
        if lieu and service:
            exists = LieuService.objects.filter(lieu=lieu, service=service, is_active=True).exists()
            if not exists:
                self.add_error('service', 'Ce service n\'est pas disponible dans ce lieu.')
        return cleaned_data


class LieuForm(forms.Form):
    name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    city = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    services = forms.ModelMultipleChoiceField(queryset=Service.objects.filter(is_active=True).order_by('name'), required=False, widget=forms.CheckboxSelectMultiple)


class CSVImportForm(forms.Form):
    MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    csv_file = forms.FileField(
        label='CSV file',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
        help_text=(
            'Columns: username, first_name, last_name, email, password, role, '
            'lieu, service, phone, is_active'
        ),
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.lower().endswith('.csv'):
            raise forms.ValidationError('Only .csv files are accepted.')
        if csv_file.size > self.MAX_SIZE_BYTES:
            raise forms.ValidationError('The file is too large (maximum 5 MB).')
        return csv_file
