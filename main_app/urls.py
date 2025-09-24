# urls.py
from django.urls import path
from . import views

app_name = "main_app"
urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('projects/', views.full_project_dashboard, name='view_project_dashboard'),
    path('api/projects-data/', views.projects_data_api, name='projects_data_api'),
    path('home/', views.projects_overview, name="landing_dashboard"),
    path('ajax/project-search/', views.ajax_project_search, name='ajax_project_search'),
]
