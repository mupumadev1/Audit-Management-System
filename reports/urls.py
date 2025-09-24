
from django.urls import path
from . import views

app_name = 'reports'
urlpatterns = [
    path('project/<int:project_id>/', views.project_report_view, name='project_report'),
    path('project/<int:project_id>/pdf/', views.project_report_pdf, name='project_report_pdf'),
    path('project/<int:project_id>/excel/', views.project_report_excel_export, name='project_report_excel'),
]