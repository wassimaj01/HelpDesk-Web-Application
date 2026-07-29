from django.urls import path

from . import views

urlpatterns = [
    # Central role-based redirect (used by LOGIN_REDIRECT_URL and the navbar)
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # Employee interface
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('tickets/create/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:pk>/cancel/', views.ticket_cancel, name='ticket_cancel'),

    # IT Admin interface
    path('admin-tickets/dashboard/', views.it_admin_dashboard, name='it_admin_dashboard'),
    path(
        'admin-tickets/<int:ticket_id>/',
        views.it_admin_ticket_detail,
        name='it_admin_ticket_detail',
    ),
    path(
        'admin-tickets/<int:ticket_id>/assign/',
        views.it_admin_assign_ticket,
        name='it_admin_assign_ticket',
    ),
    path(
        'admin-tickets/<int:ticket_id>/validate/',
        views.it_admin_validate_resolution,
        name='it_admin_validate_resolution',
    ),
    path(
       'admin-tickets/<int:ticket_id>/delete/',
       views.it_admin_delete_ticket,
       name='it_admin_delete_ticket',
    ),

    # IT Operator interface
    path('operator/dashboard/', views.operator_dashboard, name='operator_dashboard'),
    path(
        'operator/tickets/<int:ticket_id>/',
        views.operator_ticket_detail,
        name='operator_ticket_detail',
    ),
    path(
        'operator/tickets/<int:ticket_id>/resolve/',
        views.operator_mark_resolved,
        name='operator_mark_resolved',
    ),
    path(
       'operator/tickets/<int:ticket_id>/return/',
       views.operator_return_ticket,
       name='operator_return_ticket',
    ),

    # Ticket messages (AJAX)
    path('tickets/<int:ticket_id>/messages/', views.ticket_messages, name='ticket_messages'),
    path('tickets/<int:ticket_id>/messages/send/', views.ticket_send_message, name='ticket_send_message'),
]
