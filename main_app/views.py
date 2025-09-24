from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from transactions.models import SupportingDocument
from .models import Project
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout

from .services import TransactionSyncService
from .sync_tasks import sync_transactions

import logging
logger = logging.getLogger(__name__)

# Helper functions to check user roles
def is_admin(user):
    return user.is_superuser


def is_staff(user):
    return user.is_staff


# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('main_app:view_project_dashboard')
            elif user.is_staff:
                return redirect('main_app:view_project_dashboard')
        else:
            return render(request, 'main_app/login.html', {'error': 'Invalid credentials'})
    return render(request, 'main_app/login.html')


# Logout view
def logout_view(request):
    logout(request)
    return redirect('main_app:login')


# Admin dashboard view
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Admin-specific data
    context = {
        'message': 'Welcome to the Admin Dashboard',
    }
    return render(request, 'main_app/admin_dashboard.html', context)


# Staff dashboard view
@login_required
@user_passes_test(is_staff)
def staff_dashboard(request):
    # Staff-specific data
    context = {
        'message': 'Welcome to the Staff Dashboard',
    }
    return render(request, 'project_templates/full_project_dashboard.html', context)


@login_required
def projects_overview(request):
    """Main dashboard view - loads immediately with skeleton"""
    # Get filter options quickly (these should be fast queries)
    try:
        available_years = SupportingDocument.objects.values_list(
            'fiscal_year', flat=True
        ).distinct().order_by('-fiscal_year')

        available_periods = SupportingDocument.objects.values_list(
            'fiscal_period', flat=True
        ).distinct().order_by('fiscal_period')
    except Exception as e:
        print(f"Error fetching filter options: {str(e)}")
        available_years = []
        available_periods = []

    # Get current filter values
    fiscal_year = request.GET.get('fiscal_year', '')
    fiscal_period = request.GET.get('fiscal_period', '')
    search_query = request.GET.get('search', '')

    context = {
        'selected_fiscal_year': fiscal_year,
        'selected_fiscal_period': fiscal_period,
        'search_query': search_query,
        'available_years': available_years,
        'available_periods': available_periods,
    }

    return render(request, 'project_templates/landing_dashboard.html', context)


def projects_data_api(request):
    """API endpoint for fetching project data asynchronously"""
    try:
        fiscal_year = request.GET.get('fiscal_year', '')
        fiscal_period = request.GET.get('fiscal_period', '')
        search_query = request.GET.get('search', '')

        # Get all projects
        projects_queryset = Project.objects.all()

        # Apply search filter
        if search_query:
            projects_queryset = projects_queryset.filter(
                Q(project_name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # For better performance, prefetch related data
        projects_queryset = projects_queryset.prefetch_related('supportingdocument_set')

        # Calculate totals and get project stats
        total_projects = projects_queryset.count()
        total_supported_transactions = 0
        total_unsupported_transactions = 0
        total_supported_value = 0
        total_unsupported_value = 0
        fully_supported_projects = 0

        project_stats = []

        # Process projects with progress updates
        for i, project in enumerate(projects_queryset):
            try:
                stats = project.get_stats(fiscal_year=fiscal_year, fiscal_period=fiscal_period)

                total_supported_transactions += stats['supported_count']
                total_unsupported_transactions += stats['unsupported_count']
                total_supported_value += stats['supported_value']
                total_unsupported_value += stats['unsupported_value']

                # Check if project is fully supported
                if stats['unsupported_count'] == 0 and stats['total_count'] > 0:
                    fully_supported_projects += 1

                project_data = {
                    'project_name': project.project_name,
                    'supported_transactions_number': stats['supported_count'],
                    'unsupported_transactions_number': stats['unsupported_count'],
                    'supported_transactions_value': stats['supported_value'],
                    'unsupported_transactions_value': stats['unsupported_value'],
                    'total_transactions': stats['total_count'],
                    'is_fully_supported': stats['unsupported_count'] == 0 and stats['total_count'] > 0,
                    # Add URL for project detail
                    'project_url': f"/projects/project/{project.project_name}/"
                }
                project_stats.append(project_data)
            except Exception as e:
                print(f"Error calculating stats for project {project.project_name}: {str(e)}")
                continue

        # Sort by total transactions
        project_stats.sort(key=lambda x: x['total_transactions'], reverse=True)

        # Get top 10 projects
        top_projects = project_stats[:10]

        # Return JSON response
        from django.http import JsonResponse
        return JsonResponse({
            'success': True,
            'data': {
                'total_projects': total_projects,
                'fully_supported_projects': fully_supported_projects,
                'total_supported_transactions': total_supported_transactions,
                'total_unsupported_transactions': total_unsupported_transactions,
                'total_supported_value': total_supported_value,
                'total_unsupported_value': total_unsupported_value,
                'top_projects': top_projects,
            }
        })

    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def full_project_dashboard(request):
    """Full dashboard with client-side loading and skeleton content"""

    # Check if this is an AJAX request for API data
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Redirect to API endpoint for AJAX requests
        return project_dashboard_api(request)

    # For regular page loads, provide minimal context for skeleton loading
    try:
        # Get available fiscal years and periods for filters
        available_years = SupportingDocument.objects.values_list(
            'fiscal_year', flat=True
        ).distinct().order_by('-fiscal_year')

        available_periods = SupportingDocument.objects.values_list(
            'fiscal_period', flat=True
        ).distinct().order_by('fiscal_period')
    except Exception as e:
        logger.error(f"Error fetching filter options: {str(e)}")
        available_years = []
        available_periods = []

    # Minimal context - no project data loaded server-side
    context = {
        'selected_fiscal_year': request.GET.get('fiscal_year', ''),
        'selected_fiscal_period': request.GET.get('fiscal_period', ''),
        'search_query': request.GET.get('search', ''),
        'available_years': available_years,
        'available_periods': available_periods,
        'sort_by': request.GET.get('sort', 'project_name'),
        'order': request.GET.get('order', 'asc'),
        'api_endpoint': reverse('main_app:projects_data_api'),
    }

    return render(request, 'project_templates/view_project_dashboard.html', context)
def project_dashboard_api(request):
    """API endpoint for project dashboard data"""
    try:
        # Get filter parameters
        fiscal_year = request.GET.get('fiscal_year', '')
        fiscal_period = request.GET.get('fiscal_period', '')
        search_query = request.GET.get('search', '')

        # Get all projects with prefetch for better performance
        projects_queryset = Project.objects.all().select_related()

        # Apply search filter if provided
        if search_query:
            projects_queryset = projects_queryset.filter(
                Q(project_name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # Calculate stats for all projects
        project_stats = []
        failed_projects = []
        fully_supported_projects = 0

        for project in projects_queryset:
            try:
                # Get project statistics
                stats = project.get_stats(fiscal_year=fiscal_year, fiscal_period=fiscal_period)

                # Check if project is fully supported
                is_fully_supported = stats['unsupported_count'] == 0 and stats['total_count'] > 0
                if is_fully_supported:
                    fully_supported_projects += 1

                # Prepare project data
                project_data = {
                    'project_name': project.project_name,
                    'description': project.description,
                    'supported_transactions_number': stats['supported_count'],
                    'unsupported_transactions_number': stats['unsupported_count'],
                    'supported_transactions_value': stats['supported_value'],
                    'unsupported_transactions_value': stats['unsupported_value'],
                    'total_transactions': stats['total_count'],
                    'sync_status': project.sync_status,
                    'last_synced': project.last_synced.isoformat() if project.last_synced else None,
                    'is_fully_supported': is_fully_supported,
                    'project_url': f"/projects/project/{project.project_name}/"
                }
                project_stats.append(project_data)

            except Exception as e:
                logger.error(f"Error calculating stats for project {project.project_name}: {str(e)}")
                failed_projects.append(project.project_name)

                # Add project with zero stats to maintain consistency
                project_data = {
                    'project_name': project.project_name,
                    'description': project.description,
                    'supported_transactions_number': 0,
                    'unsupported_transactions_number': 0,
                    'supported_transactions_value': 0,
                    'unsupported_transactions_value': 0,
                    'total_transactions': 0,
                    'sync_status': project.sync_status,
                    'last_synced': project.last_synced.isoformat() if project.last_synced else None,
                    'has_error': True,
                    'is_fully_supported': False,
                    'project_url': reverse('transactions:project_dashboard', args=[project.project_name])
                }
                project_stats.append(project_data)

        # Sort projects if requested
        sort_by = request.GET.get('sort', 'project_name')
        reverse_sort = request.GET.get('order', 'asc') == 'desc'

        # Define sortable fields
        numeric_fields = [
            'supported_transactions_number',
            'unsupported_transactions_number',
            'supported_transactions_value',
            'unsupported_transactions_value',
            'total_transactions'
        ]

        string_fields = ['project_name', 'description', 'sync_status']

        try:
            if sort_by in numeric_fields:
                project_stats.sort(
                    key=lambda x: x.get(sort_by, 0),
                    reverse=reverse_sort
                )
            elif sort_by in string_fields:
                project_stats.sort(
                    key=lambda x: x.get(sort_by, ''),
                    reverse=reverse_sort
                )
            elif sort_by == 'last_synced':
                project_stats.sort(
                    key=lambda x: x.get('last_synced', '') or '',
                    reverse=reverse_sort
                )
            else:
                # Default to project_name if invalid sort field
                project_stats.sort(
                    key=lambda x: x.get('project_name', ''),
                    reverse=reverse_sort
                )
        except Exception as e:
            logger.error(f"Error sorting projects: {str(e)}")
            # Fall back to default sorting
            project_stats.sort(key=lambda x: x.get('project_name', ''))

        # Prepare response data
        response_data = {
            'projects': project_stats,
            'summary': {
                'total_projects': len(project_stats),
                'fully_supported_projects': fully_supported_projects,
                'failed_projects': failed_projects,
                'total_supported_transactions': sum(p['supported_transactions_number'] for p in project_stats),
                'total_unsupported_transactions': sum(p['unsupported_transactions_number'] for p in project_stats),
                'total_supported_value': sum(p['supported_transactions_value'] for p in project_stats),
                'total_unsupported_value': sum(p['unsupported_transactions_value'] for p in project_stats),
            },
            'filters': {
                'fiscal_year': fiscal_year,
                'fiscal_period': fiscal_period,
                'search_query': search_query,
                'sort_by': sort_by,
                'order': request.GET.get('order', 'asc')
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in project_dashboard_api: {str(e)}")
        return JsonResponse({
            'error': 'An error occurred while fetching project data',
            'projects': [],
            'summary': {
                'total_projects': 0,
                'fully_supported_projects': 0,
                'failed_projects': [],
                'total_supported_transactions': 0,
                'total_unsupported_transactions': 0,
                'total_supported_value': 0,
                'total_unsupported_value': 0,
            }
        }, status=500)
@login_required
def ajax_project_search(request):
    """AJAX endpoint for project search suggestions"""
    query = request.GET.get('q', '')

    if len(query) < 2:
        return JsonResponse({'results': []})

    projects = Project.objects.filter(
        Q(project_name__icontains=query) |
        Q(description__icontains=query)
    )[:10]

    results = [
        {
            'id': project.project_id,
            'name': project.project_name,
            'description': project.description[:100] + '...' if len(project.description) > 100 else project.description
        }
        for project in projects
    ]

    return JsonResponse({'results': results})
