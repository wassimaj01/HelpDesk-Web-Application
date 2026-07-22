from django import forms
from django.contrib.auth.models import User

from tickets.models import LieuService
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
    lieu_service = forms.ModelChoiceField(queryset=LieuService.objects.none(), label='Location / Service', widget=forms.Select(attrs={'class': 'form-select'}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active = forms.BooleanField(required=False, initial=True, label='Active', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lieu_service'].queryset = _active_lieu_services()

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
        return cleaned_data


class UserUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    lieu_service = forms.ModelChoiceField(queryset=LieuService.objects.none(), label='Location / Service', widget=forms.Select(attrs={'class': 'form-select'}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_active = forms.BooleanField(required=False, label='Active', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, target_user=None, **kwargs):
        self.target_user = target_user
        super().__init__(*args, **kwargs)
        self.fields['lieu_service'].queryset = _active_lieu_services()

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and self.target_user is not None:
            clash = User.objects.filter(email__iexact=email).exclude(pk=self.target_user.pk)
            if clash.exists():
                raise forms.ValidationError('A user with this email already exists.')
        return email


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
