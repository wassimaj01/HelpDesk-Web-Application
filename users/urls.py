from django.urls import path

from . import views

urlpatterns = [
    path('', views.user_management_dashboard, name='user_management_dashboard'),
    path('create/', views.user_create, name='user_create'),
    path('<int:user_id>/', views.user_detail, name='user_detail'),
    path('<int:user_id>/edit/', views.user_update, name='user_update'),
    path('<int:user_id>/deactivate/', views.user_deactivate, name='user_deactivate'),
    path('import-csv/', views.user_import_csv, name='user_import_csv'),

    # Lieu management
    path('lieux/', views.lieu_list, name='lieu_list'),
    path('lieux/create/', views.lieu_create, name='lieu_create'),
    path('lieux/<int:lieu_id>/edit/', views.lieu_edit, name='lieu_edit'),
    path('lieux/<int:lieu_id>/delete/', views.lieu_delete, name='lieu_delete'),

    # AJAX
    path('ajax/services-by-lieu/<int:lieu_id>/', views.services_by_lieu, name='services_by_lieu'),
]
