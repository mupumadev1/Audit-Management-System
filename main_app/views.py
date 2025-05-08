from django.shortcuts import render
from .models import Project # Import project model 
from django.db.models import Sum

def landing_dashboard(request):
    # Sample data
    projects = [
        { 'project_name': "Project Alpha", 'supported_transactions': 120, 'supported_value': 25000, 'unsupported_transactions': 5, 'unsupported_value': 1000 },
        { 'project_name': "Project Beta", 'supported_transactions': 85, 'supported_value': 18000, 'unsupported_transactions': 2, 'unsupported_value': 500 },
        { 'project_name': "Project Gamma", 'supported_transactions': 200, 'supported_value': 42000, 'unsupported_transactions': 8, 'unsupported_value': 1500 },
        { 'project_name': "Project Delta", 'supported_transactions': 95, 'supported_value': 19000, 'unsupported_transactions': 1, 'unsupported_value': 200 },
        { 'project_name': "Project Echo", 'supported_transactions': 150, 'supported_value': 30000, 'unsupported_transactions': 6, 'unsupported_value': 1100 },
        { 'project_name': "Project Fox", 'supported_transactions': 70, 'supported_value': 15000, 'unsupported_transactions': 0, 'unsupported_value': 0 },
        { 'project_name': "Project Golf", 'supported_transactions': 110, 'supported_value': 22000, 'unsupported_transactions': 3, 'unsupported_value': 600 },
    ]

    # Totals
    total_supported_transactions = sum(p['supported_transactions'] for p in projects)
    total_supported_value = sum(p['supported_value'] for p in projects)
    total_unsupported_transactions = sum(p['unsupported_transactions'] for p in projects)
    total_unsupported_value = sum(p['unsupported_value'] for p in projects)

    # Only first 5 projects
    top_projects = projects[:5]

    context = {
        'total_supported_transactions': total_supported_transactions,
        'total_supported_value': total_supported_value,
        'total_unsupported_transactions': total_unsupported_transactions,
        'total_unsupported_value': total_unsupported_value,
        'top_projects': top_projects,
    }
    return render(request, 'main_app/landing_dashboard.html', context)

def view_project_dashboard(request):
    # Placeholder data (replace with actual data from Sage)
    projects = [
        { 'project_name': "Project Alpha", 'supported_transactions': 120, 'supported_value': 25000, 'unsupported_transactions': 5, 'unsupported_value': 1000 },
        { 'project_name': "Project Beta", 'supported_transactions': 85, 'supported_value': 18000, 'unsupported_transactions': 2, 'unsupported_value': 500 },
        { 'project_name': "Project Gamma", 'supported_transactions': 200, 'supported_value': 42000, 'unsupported_transactions': 8, 'unsupported_value': 1500 },
        { 'project_name': "Project Delta", 'supported_transactions': 95, 'supported_value': 19000, 'unsupported_transactions': 1, 'unsupported_value': 200 },
        { 'project_name': "Project Echo", 'supported_transactions': 150, 'supported_value': 30000, 'unsupported_transactions': 6, 'unsupported_value': 1100 },
        { 'project_name': "Project Fox", 'supported_transactions': 70, 'supported_value': 15000, 'unsupported_transactions': 0, 'unsupported_value': 0 },
        { 'project_name': "Project Golf", 'supported_transactions': 110, 'supported_value': 22000, 'unsupported_transactions': 3, 'unsupported_value': 600 },
        { 'project_name': "Project Hotel", 'supported_transactions': 180, 'supported_value': 38000, 'unsupported_transactions': 7, 'unsupported_value': 1300 },
        { 'project_name': "Project India", 'supported_transactions': 60, 'supported_value': 12000, 'unsupported_transactions': 2, 'unsupported_value': 400 },
        { 'project_name': "Project Juliet", 'supported_transactions': 130, 'supported_value': 27000, 'unsupported_transactions': 4, 'unsupported_value': 800 },
    ]


    #If you are using a model, you would get the data like this
    # projects = Project.objects.all()

    # Calculate summary (you can do this in the template, but it's often better in the view)
    # total_supported_transactions = projects.aggregate(Sum('supported_transactions'))['supported_transactions__sum'] or 0
    # total_supported_value = projects.aggregate(Sum('supported_value'))['supported_value__sum'] or 0
    # total_unsupported_transactions = projects.aggregate(Sum('unsupported_transactions'))['unsupported_transactions__sum'] or 0
    # total_unsupported_value = projects.aggregate(Sum('unsupported_value'))['unsupported_value__sum'] or 0
    #
    # summary_data = {
    #     'total_supported_transactions': total_supported_transactions,
    #     'total_supported_value': total_supported_value,
    #     'total_unsupported_transactions': total_unsupported_transactions,
    #     'total_unsupported_value': total_unsupported_value,
    # }

    context = {
        'projects': projects,
        # 'summary_data': summary_data, # Pass the summary if calculated here
    }
    return render(request, 'project_templates/view_project_dashboard.html', context)