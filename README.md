# GPI Ticketing

Internal IT ticket management system built with Django (MVT), using PostgreSQL and
Django's built-in authentication (`auth_user`, `auth_group`, `auth_user_groups`).

## Requirements

- Python 3.10+
- PostgreSQL (server running locally or reachable)
- pip

## 1. Clone and set up a virtual environment

```powershell
cd C:\Users\m\Desktop\GTI
python -m venv venv
venv\Scripts\Activate.ps1
```

## 2. Install dependencies

```powershell
pip install -r requirements.txt
```

## 3. Configure environment variables

Copy the example file and adjust values if needed:

```powershell
Copy-Item .env.example .env
```

`.env` contents:

```
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=gpi_ticketing_db
DB_USER=gpi_user
DB_PASSWORD=gpi_password
DB_HOST=localhost
DB_PORT=5432
```

## 4. Create the PostgreSQL database and user

Run these with a PostgreSQL superuser (adjust host/password as needed):

```powershell
psql -U postgres -h localhost -d template1 -c "CREATE USER gpi_user WITH PASSWORD 'gpi_password';"
psql -U postgres -h localhost -d template1 -c "CREATE DATABASE gpi_ticketing_db OWNER gpi_user;"
psql -U postgres -h localhost -d template1 -c "GRANT ALL PRIVILEGES ON DATABASE gpi_ticketing_db TO gpi_user;"
```

## 5. Run migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

## 6. Seed demo data

Creates groups, demo users, lieux, services, problem types, and sample tickets.

```powershell
python manage.py seed_demo_data
```

Seeded accounts (all use password `password123`):

| Username    | Role        | Notes                                              |
|-------------|-------------|-----------------------------------------------------|
| superadmin  | Super_Admin | `is_staff=True`, `is_superuser=True`                 |
| aziz        | IT_Admin    | Network / telecom / helpdesk problems                |
| said        | IT_Admin    | Application / database / software problems           |
| operator1   | IT_Operator | Resolves tickets assigned by IT admins                |
| operator2   | IT_Operator | Resolves tickets assigned by IT admins                |
| employee1   | Employee    | Creates tickets                                       |

## 7. Run the development server

```powershell
python manage.py runserver
```

Then open:

- Admin site: http://127.0.0.1:8000/admin/ (log in as `superadmin` / `password123`)

## Project structure

```
gpi_ticketing/        # Project settings, root URLconf
tickets/               # Main app: models, admin, management commands
  management/commands/seed_demo_data.py
  models.py
  admin.py
```

## Notes

- Custom User model is intentionally NOT used — Django's built-in `User` and `Group`
  models are used directly, with roles managed via Groups (`Employee`, `IT_Admin`,
  `IT_Operator`, `Super_Admin`).
- Business workflow (ticket creation, assignment, resolution, validation, closing)
  is implemented as methods on the `Ticket` model (`assign_to_operator`,
  `mark_as_resolved`, `accept_resolution`, `refuse_resolution`), each recording an
  entry in `TicketHistory`.
