"""CSV bulk-import logic for the IT_Admin user-management interface.

Expected columns (header row required):
    username,first_name,last_name,email,password,role,lieu,service,phone,is_active

Only Employee, IT_Admin and IT_Operator roles can be imported this way;
Super_Admin/superuser accounts must always be created through the Django
admin. Each row is created in its own transaction.atomic() block so a
failure on one row never leaves a half-created user (User without a
UserProfile, etc.) while still allowing the rest of the batch to succeed.
"""

import csv
import io

from django.contrib.auth.models import Group, User
from django.db import transaction

from .models import Lieu, LieuService, Service, UserProfile
from .permissions import MANAGEABLE_ROLES

REQUIRED_COLUMNS = {'username', 'password', 'role', 'lieu', 'service'}
TRUE_VALUES = {'true', '1', 'yes', 'y'}


def _parse_bool(value, default=True):
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in TRUE_VALUES


def _empty_result(fatal_error):
    return {
        'created': [],
        'skipped': [],
        'created_count': 0,
        'skipped_count': 0,
        'fatal_error': fatal_error,
    }


def import_users_from_csv(csv_file):
    """Parse an uploaded CSV file and create users from its rows.

    Returns a dict:
        created: list of usernames successfully created
        skipped: list of {'row': 'Row N', 'reason': '...'}
        created_count / skipped_count: convenience counters
        fatal_error: set only if the whole file could not be processed
                     at all (bad encoding, empty file, missing columns)
    """
    try:
        raw_bytes = csv_file.read()
    except Exception as exc:
        return _empty_result(f'Could not read the uploaded file: {exc}')

    try:
        decoded = raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        return _empty_result(
            'The file could not be decoded as UTF-8. Please re-save it as a UTF-8 CSV.'
        )

    reader = csv.DictReader(io.StringIO(decoded))

    if reader.fieldnames is None:
        return _empty_result('The CSV file appears to be empty.')

    header = {(name or '').strip() for name in reader.fieldnames}
    missing_columns = REQUIRED_COLUMNS - header
    if missing_columns:
        return _empty_result(
            f"Missing required column(s): {', '.join(sorted(missing_columns))}."
        )

    created = []
    skipped = []

    for index, row in enumerate(reader, start=2):  # row 1 is the header
        row_label = f'Row {index}'

        # Skip fully empty rows (e.g. trailing blank lines).
        if not any((value or '').strip() for value in row.values() if value is not None):
            continue

        username = (row.get('username') or '').strip()
        password = (row.get('password') or '').strip()
        role = (row.get('role') or '').strip()
        lieu_name = (row.get('lieu') or '').strip()
        service_name = (row.get('service') or '').strip()
        first_name = (row.get('first_name') or '').strip()
        last_name = (row.get('last_name') or '').strip()
        email = (row.get('email') or '').strip()
        phone = (row.get('phone') or '').strip()
        is_active = _parse_bool(row.get('is_active'), default=True)

        if not username:
            skipped.append({'row': row_label, 'reason': 'Missing username.'})
            continue
        if not password:
            skipped.append({'row': row_label, 'reason': f'Missing password for "{username}".'})
            continue
        if not role:
            skipped.append({'row': row_label, 'reason': f'Missing role for "{username}".'})
            continue
        if role not in MANAGEABLE_ROLES:
            skipped.append({
                'row': row_label,
                'reason': (
                    f'Invalid role "{role}" for "{username}". '
                    f'Must be one of {", ".join(MANAGEABLE_ROLES)}.'
                ),
            })
            continue
        if not lieu_name:
            skipped.append({'row': row_label, 'reason': f'Missing lieu for "{username}".'})
            continue
        if not service_name:
            skipped.append({'row': row_label, 'reason': f'Missing service for "{username}".'})
            continue

        if User.objects.filter(username=username).exists():
            skipped.append({'row': row_label, 'reason': f'Username "{username}" already exists.'})
            continue
        if email and User.objects.filter(email__iexact=email).exists():
            skipped.append({'row': row_label, 'reason': f'Email "{email}" already exists.'})
            continue

        group = Group.objects.filter(name=role).first()
        if group is None:
            skipped.append({'row': row_label, 'reason': f'Group "{role}" does not exist.'})
            continue

        lieu = Lieu.objects.filter(name=lieu_name).first()
        if lieu is None:
            skipped.append({'row': row_label, 'reason': f'Lieu "{lieu_name}" not found.'})
            continue

        service = Service.objects.filter(name=service_name).first()
        if service is None:
            skipped.append({'row': row_label, 'reason': f'Service "{service_name}" not found.'})
            continue

        lieu_service = LieuService.objects.filter(lieu=lieu, service=service).first()
        if lieu_service is None:
            skipped.append({
                'row': row_label,
                'reason': (
                    f'No Lieu/Service combination exists for '
                    f'"{lieu_name}" + "{service_name}".'
                ),
            })
            continue

        try:
            with transaction.atomic():
                user = User.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=is_active,
                    is_staff=False,
                    is_superuser=False,
                )
                user.set_password(password)
                user.save()
                user.groups.add(group)
                UserProfile.objects.create(
                    user=user,
                    lieu_service=lieu_service,
                    phone=phone or None,
                    is_active=is_active,
                )
        except Exception as exc:
            skipped.append({'row': row_label, 'reason': f'Could not create "{username}": {exc}'})
            continue

        created.append(username)

    return {
        'created': created,
        'skipped': skipped,
        'created_count': len(created),
        'skipped_count': len(skipped),
        'fatal_error': None,
    }
