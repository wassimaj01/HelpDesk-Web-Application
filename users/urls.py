from django.urls import path

from . import views

urlpatterns = [
    path('', views.user_management_dashboard, name='user_management_dashboard'),
    path('create/', views.user_create, name='user_create'),
    path('<int:user_id>/', views.user_detail, name='user_detail'),
    path('<int:user_id>/edit/', views.user_update, name='user_update'),
    path('<int:user_id>/deactivate/', views.user_deactivate, name='user_deactivate'),
    path('import-csv/', views.user_import_csv, name='user_import_csv'),
]
