
from django.urls import path

from audit_management_system import settings
from transactions import views
from django.conf.urls.static import static
app_name = "transactions"
urlpatterns = [
    path('project/<str:project_name>/', views.admin_home, name='project_dashboard'),
    path('project/api/<str:project_name>/', views.admin_home_api, name='project_dashboard'),
    path('save-transaction-comment/', views.save_transaction_comment, name='save_transaction_comment'),
    path('delete-transaction-comment/', views.delete_transaction_comment, name='delete_transaction_comment'),
    path('delete-transaction-file/<int:file_id>/', views.delete_transaction_file, name='delete_transaction_file'),
    path('/transaction-history/', views.get_transaction_comment_history, name='get_transaction_comment_history'),
    path('upload-document/<str:batchnbr>/<str:entrynbr>/<str:project_name>/', views.upload_file, name='upload_file'),
    path('external-files/<path:file_path>/', views.serve_external_file, name='serve_external_file'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
