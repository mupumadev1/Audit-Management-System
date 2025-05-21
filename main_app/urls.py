# urls.py
from django.urls import path
from . import views

app_name = "main_app"
urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.landing_dashboard, name="landing_dashboard"),
    path('projects/', views.view_project_dashboard, name='view_project_dashboard'),
]
