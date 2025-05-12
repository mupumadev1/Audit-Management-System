# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('landing-dashboard/', views.landing_dashboard, name="landing_dashboard"),
    path('view-project-dashboard/', views.view_project_dashboard, name='view_project_dashboard'),
]