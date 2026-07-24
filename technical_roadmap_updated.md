# Technical Roadmap — GPI Ticketing (gpi_ticketing)

Date: 2026-07-23T20:13:15+01:00

Purpose
-------
This document records the project's history, architecture, modules, models, database layout, permissions and an overview of every major URL/view/template combination implemented to date. It also points to the call flow diagrams that summarize the main interactions between users, views, forms and models.

Table of contents
-----------------
- Project timeline (what was done, step-by-step)
- Applications / modules and responsibilities
- Models and database (tables and relationships)
- User roles and permissions (what each role can/cannot do)
- URLs, views and templates (complete mapping)
- Major business flows (how the pieces interact)
- Notes, testing and next steps

Project timeline (step-by-step)
-------------------------------
This timeline documents changes from the initial project creation through the latest edits.

1. Project creation
   - Django project `gpi_ticketing` created.
   - App `tickets` scaffolded with core models: Lieu, Service, LieuService, UserProfile, ProblemType, Ticket, TicketHistory.
   - PostgreSQL settings added and python-decouple used for .env configuration.
   - Initial migrations created (tickets migrations) to build database tables for models above.

2. Basic ticket workflows implemented
   - Employee interfaces: create ticket, view tickets, edit and cancel own tickets.
   - IT_Admin interfaces: dashboard listing tickets routed to them; assign tickets to operators; validate/accept/refuse resolutions.
   - IT_Operator interfaces: operator dashboard, mark ticket resolved.
   - TicketHistory entries created at important transitions.

3. Authentication and roles
   - Used Django built-in User and Group models (no custom user model).
   - Groups defined: Employee, IT_Admin, IT_Operator, Super_Admin.
   - UserProfile added and linked to User for professional metadata (lieu_service, phone, is_active).

4. User management (initial)
   - A custom user-management UI was created inside the tickets app (user_views.py, forms in tickets/forms.py).
   - Features: create user, edit user, deactivate/reactivate, CSV import.
   - CSV import logic implemented (tickets/csv_import.py) with row-level validation and transactional creation.

5. Operator return & Admin hard-delete (feature additions)
   - Operator return: operator_return_ticket view allows operators to return assigned tickets with a reason, changes state back to CREATED and records TicketHistory OPERATOR_RETURNED.
   - IT Admin hard-delete: it_admin_delete_ticket view allows responsible admins to hard-delete tickets they own (ticket.delete()).

6. Refactor: move user-management to `users` app
   - Created `users` app and moved user-management views and forms there.
   - Updated project URLs to include users.urls and removed user-management routes from tickets.urls.
   - Kept UserProfile model in tickets.models to avoid migration complexity.
   - Created a compatibility shim then removed it (tickets/user_views.py) to surface stale imports.

7. Improvements: Lieu management and dependent dropdowns
   - Added Lieu management: list, create, delete (users.views: lieu_list, lieu_create, lieu_delete).
   - Enhanced user create/update forms to separate Lieu and Service fields; added AJAX endpoint (services_by_lieu) to populate Services for a chosen Lieu and server-side validation to resolve LieuService.
   - Fixed form validation so service choices rebuilt during POST based on selected Lieu.

8. Lieu edit (latest)
   - Implemented lieu_edit (users.views) and UI changes to allow editing a Lieu and its available Services. Updates create/reactivate/deactivate LieuService rows to match selection.

Applications / modules and responsibilities
------------------------------------------
- gpi_ticketing (project root)
  - settings.py: Django settings, INSTALLED_APPS includes `tickets` and `users`.
  - urls.py: project-level routing for login/logout, users app and tickets app.

- tickets (app)
  - models.py: core domain models (Lieu, Service, LieuService, UserProfile, ProblemType, Ticket, TicketHistory).
  - views.py: all ticket-related views (employee/IT_Admin/operator workflows, assignments, validations, ticket CRUD). Contains business logic and calls to models to transition ticket states and create TicketHistory entries.
  - forms.py: ticket-related forms (TicketCreateForm, TicketEditForm, AssignTicketForm, ValidateResolutionForm, ResolveTicketForm). Also earlier contained user forms before the refactor.
  - csv_import.py: CSV parsing and bulk user creation helper used by the users app.
  - templates/tickets/: templates for ticket lists, details, operator/admin dashboards, confirmation pages.
  - management/commands/seed_demo_data.py: seeds initial data (lieux, services, lieu_services, users, problem types, sample tickets).

- users (app)
  - views.py: user management (user_management_dashboard, user_create, user_update, user_detail, user_deactivate, user_import_csv), Lieu management (lieu_list, lieu_create, lieu_edit, lieu_delete) and AJAX endpoint (services_by_lieu).
  - forms.py: UserCreateForm, UserUpdateForm (separate lieu and service fields), LieuForm (create/edit) and CSVImportForm.
  - urls.py: routes prefixed by /users/ (keeps original route names used by templates).
  - templates/users/: custom templates for user management and lieux (user_create.html, user_update.html, user_management_dashboard.html, user_detail.html, import_result.html, lieu_list.html, lieu_form.html, lieu_confirm_delete.html).

Database models and relationships
--------------------------------
All models live in tickets.models (so migrations are centralized there). Key tables and relationships:

- auth_user (built-in Django table)
  - username, password, email, first_name, last_name, is_active, is_staff, is_superuser, etc.

- auth_group, auth_user_groups (Django built-in)
  - Groups: Employee, IT_Admin, IT_Operator, Super_Admin

- tickets_lieu
  - id, name, address, city, description, is_active, created_at, updated_at
  - __str__ is the lieu name

- tickets_service
  - id, name, code (unique), description, is_active, created_at, updated_at
  - Example rows: Adhésion, Liquidation, Informatique

- tickets_lieuservice
  - id, lieu_id (FK -> tickets_lieu), service_id (FK -> tickets_service), is_active, created_at, updated_at
  - unique_together (lieu, service)
  - Used to enumerate which services are available at each Lieu

- tickets_userprofile
  - id, user_id (OneToOne FK -> auth_user), lieu_service_id (FK -> tickets_lieuservice), phone, is_active, created_at, updated_at
  - Stores the employee's professional metadata and which LieuService they belong to

- tickets_problemtype
  - id, label, description, category (enum), responsible_admin (FK -> auth_user), is_active, created_at, updated_at
  - ProblemType determines ticket category and default responsible_admin

- tickets_ticket
  - id, reference, problem_type_id (FK -> tickets_problemtype), description, category, status, created_by (FK -> auth_user), requester_lieu_service_id (FK -> tickets_lieuservice), responsible_admin (FK -> auth_user), assigned_to (FK -> auth_user nullable), assigned_by (FK -> auth_user nullable), assigned_at, resolved_by, resolved_at, admin_validation_decision, validated_by, validated_at, closed_by, closed_at, created_at, updated_at
  - Central table representing tickets

- tickets_tickethistory
  - id, ticket_id (FK -> tickets_ticket), action (enum), old_status, new_status, old_assigned_to (FK -> auth_user nullable), new_assigned_to (FK -> auth_user nullable), changed_by (FK -> auth_user), comment, created_at
  - Audit trail for every important action on tickets

Notes on database integrity and cascading
- Many FK relationships use on_delete=PROTECT (for critical relations like ticket.created_by and ticket.responsible_admin) to prevent accidental deletion of referenced users.
- Lieu -> LieuService uses CASCADE, so deleting a Lieu removes its LieuService rows unless PROTECT blocks deletion due to other dependent records (users/tickets referencing the LieuService).
- Deleting tickets deletes associated TicketHistory rows (cascade).

User roles and permissions (what each role can/cannot do)
--------------------------------------------------------
- Super_Admin (a Django superuser)
  - Full access to Django admin site.
  - Can manage any user, groups, and all models via Django admin.
  - Access to the custom user-management pages because can_manage_users() checks user.is_superuser.
  - Recommended: used for technical administration only.

- IT_Admin (group member)
  - Access to IT admin dashboard (it_admin_dashboard).
  - Can view tickets routed to them, assign tickets to operators, validate or refuse resolutions.
  - Can manage application users via the custom Users UI (create, edit, deactivate, bulk-import). Cannot create superusers or set is_staff/is_superuser via the custom UI.
  - Can manage Lieux (list/create/edit/delete) via the UI.
  - Can hard-delete tickets **only** if responsible_admin == request.user (from the custom admin interface), not other admins' tickets.

- IT_Operator (group member)
  - Access to operator dashboard and tickets assigned to them.
  - Can mark tickets assigned to them as resolved.
  - Can return a ticket assigned to them (operator_return_ticket) with a mandatory reason; this sets status back to CREATED and clears assignment.
  - Cannot manage users or lieux.

- Employee (group member)
  - Can create tickets, edit or cancel own tickets when in CREATED status, view own tickets.
  - Cannot assign, reassign, resolve, return, or hard-delete tickets.
  - Cannot access user-management or lieu-management UIs.

Permission helpers
- tickets.permissions.user_in_group(user, group_name)
- is_it_admin(user) / is_it_operator(user) / is_employee(user)
- MANAGEABLE_ROLES = ['Employee', 'IT_Admin', 'IT_Operator']
- can_manage_users(user): True if user.is_superuser or is_it_admin(user)
- role_required decorator enforces arbitrary checks (used alongside login_required)

URL map (major routes and names)
--------------------------------
- Authentication
  - /accounts/login/  (name='login') — LoginView using templates/registration/login.html
  - /accounts/logout/ (name='logout') — logout_view (POST preferred; GET handled gracefully)

- Users / User-management (users app)
  - /users/                          name='user_management_dashboard'
  - /users/create/                   name='user_create'
  - /users/<int:user_id>/            name='user_detail'
  - /users/<int:user_id>/edit/       name='user_update'
  - /users/<int:user_id>/deactivate/ name='user_deactivate'
  - /users/import-csv/               name='user_import_csv'

- Lieux (within users app)
  - /users/lieux/                    name='lieu_list'
  - /users/lieux/create/             name='lieu_create'
  - /users/lieux/<int:lieu_id>/edit/ name='lieu_edit'
  - /users/lieux/<int:lieu_id>/delete/ name='lieu_delete'
  - /users/ajax/services-by-lieu/<int:lieu_id>/ name='services_by_lieu' (AJAX JSON)

- Tickets (tickets app)
  - /dashboard/                       name='dashboard' (redirects based on role)
  - /employee/dashboard/              name='employee_dashboard'
  - /tickets/create/                  name='ticket_create'
  - /tickets/<int:pk>/                name='ticket_detail'
  - /tickets/<int:pk>/edit/           name='ticket_edit'
  - /tickets/<int:pk>/cancel/         name='ticket_cancel'

  - /admin-tickets/dashboard/         name='it_admin_dashboard'
  - /admin-tickets/<int:ticket_id>/   name='it_admin_ticket_detail'
  - /admin-tickets/<int:ticket_id>/assign/   name='it_admin_assign_ticket'
  - /admin-tickets/<int:ticket_id>/validate/ name='it_admin_validate_resolution'
  - /admin-tickets/<int:ticket_id>/delete/   name='it_admin_delete_ticket'

  - /operator/dashboard/              name='operator_dashboard'
  - /operator/tickets/<int:ticket_id>/name='operator_ticket_detail'
  - /operator/tickets/<int:ticket_id>/resolve/ name='operator_mark_resolved'
  - /operator/tickets/<int:ticket_id>/return/  name='operator_return_ticket'

Views used (major)
-------------------
- users.views.user_management_dashboard — list users and basic stats
- users.views.user_create — form to create a user (resolves LieuService from lieu+service)
- users.views.user_update — edit user (resolves LieuService)
- users.views.user_detail — shows user info and profile
- users.views.user_deactivate — toggle active state for user/profile
- users.views.user_import_csv — upload CSV to create users in bulk
- users.views.lieu_list — list Lieux with services and actions
- users.views.lieu_create — create Lieu and LieuService rows
- users.views.lieu_edit — edit Lieu and synchronize LieuService rows
- users.views.lieu_delete — confirm and delete Lieu (handle ProtectedError)
- users.views.services_by_lieu — AJAX endpoint that returns services for a Lieu

- tickets.views.dashboard_redirect — role-based redirect after login
- tickets.views.ticket_create — employee ticket creation
- tickets.views.ticket_edit / ticket_cancel — employee edit/cancel
- tickets.views.it_admin_dashboard — tickets for responsible admin
- tickets.views.it_admin_assign_ticket — assign to operator
- tickets.views.it_admin_validate_resolution — accept/refuse resolution
- tickets.views.it_admin_delete_ticket — hard delete by responsible admin
- tickets.views.operator_mark_resolved — operator marks assigned ticket resolved
- tickets.views.operator_return_ticket — operator returns ticket (OPERATOR_RETURNED history)

Templates used (major)
----------------------
- templates/base.html — main layout and navbar (includes POST logout form and role flags via context processor)
- templates/registration/login.html — login form

- templates/users/
  - user_management_dashboard.html
  - user_create.html
  - user_update.html
  - user_detail.html
  - user_import_csv.html
  - import_result.html
  - _deactivate_modal.html
  - lieu_list.html
  - lieu_form.html
  - lieu_confirm_delete.html

- templates/tickets/
  - employee dashboard, operator dashboard, it_admin dashboard templates
  - ticket_create.html, ticket_detail.html, operator_ticket_detail.html, it_admin_ticket_detail.html
  - operator_return_ticket.html, it_admin_delete_ticket.html (confirmations)

Major business flows (high level)
---------------------------------
- Ticket creation (employee)
  - User -> GET /tickets/create/ -> tickets.views.ticket_create -> tickets.forms.TicketCreateForm -> Ticket.create_for_employee -> TicketHistory entries -> redirect

- Assignment (admin)
  - Admin -> it_admin_dashboard -> choose ticket -> it_admin_assign_ticket (form) -> assign operator -> Ticket.assign_to_operator -> TicketHistory (TICKET_ASSIGNED or TICKET_REASSIGNED)

- Operator return
  - Operator -> operator_ticket_detail -> Return -> operator_return_ticket (POST with reason) -> Ticket updated to CREATED and assignment cleared -> TicketHistory(OPERATOR_RETURNED)

- Admin hard delete
  - Admin -> it_admin_ticket_detail -> Delete -> it_admin_delete_ticket (POST confirm) -> ticket.delete() -> redirect

- User management manual create
  - IT_Admin -> /users/create/ -> users.forms.UserCreateForm (select lieu then service via AJAX) -> server resolves LieuService and creates User + UserProfile

- CSV import
  - IT_Admin -> /users/import-csv/ -> upload CSV -> tickets.csv_import.import_users_from_csv handles parsing, validation and transactional row creation

- Lieu lifecycle
  - Create: users.views.lieu_create creates Lieu and LieuService rows for selected services (get_or_create; reactivate if needed)
  - Edit: users.views.lieu_edit updates Lieu fields, get_or_create for newly selected services, and deactivates previously selected services no longer chosen
  - Delete: users.views.lieu_delete attempts to delete the Lieu; shows friendly message if ProtectedError/IntegrityError prevents deletion

Testing & verification performed
--------------------------------
- Ran `python manage.py check` after structural changes — no system check errors reported.
- Manual UI changes updated for dependent dropdowns and Lieu management; templates include small vanilla JS for AJAX-based service loading.

Next recommended actions
------------------------
- Add unit tests for:
  - User create/update resolving LieuService
  - AJAX services_by_lieu endpoint
  - Lieu create/edit/delete flows including LieuService synchronization
  - Operator return and IT Admin delete behaviors
- Consider adding staging/CI to run the Django test suite automatically.

Appendix
--------
- Call flow diagrams are available in call_flow_diagram.md which contains ASCII diagrams of the main request/response flows.

