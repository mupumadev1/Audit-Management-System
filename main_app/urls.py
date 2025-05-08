# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('landing-dashboard/', views.landing_dashboard, name="landing_dashboard"),
    path('view-project-dashboard/', views.view_project_dashboard, name='view_project_dashboard'),
]