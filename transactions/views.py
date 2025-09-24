from django.core.paginator import *
from django.db.models import Sum, Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from main_app.models import Project, DatabaseMapping
from main_app.sync_tasks import sync_transactions
from transactions.forms import UploadFileForm
from transactions.models import Glpost, SupportingDocument, Comments, SupportingDocumentFile

from django.db.models import Q
from datetime import datetime
from collections import defaultdict

from transactions.services import ProjectSyncService


# Updated view function with multi-filter support
def admin_home(request, project_name):

    return render(request, 'home_content.html')


def admin_home_api(request, project_name):
    sync_transactions()
    # Redirect to the current year and period if not provided

    current_date = datetime.now()
    year = str(current_date.year)
    fiscal_period = str(current_date.month).zfill(2)
    # Start with base queryset

    db = DatabaseMapping.objects.get(project_name=project_name)
    gl_transactions_list = Glpost.objects.using(f'{db.sql_server_db}').filter(fiscalyr=year, srceledger='EN').order_by(
        '-jrnldate', 'batchnbr')

    comments = Comments.objects.all()
    comments_dict = {
        f"{comment.batchnbr}-{comment.entrynbr}": comment.text
        for comment in comments
    }
    service = ProjectSyncService()
    service.sync_transactions(project_name=project_name, fiscal_year=year, fiscal_period=fiscal_period, dry_run=False)
    # Get project instance first
    project = Project.objects.get(project_name=project_name)

    # Get supporting documents filtered by project
    docs = SupportingDocument.objects.filter(project=project).select_related('project')

    # Create set of supported composite keys (batchnbr, entrynbr) as tuples
    docs_composite_keys = set((doc.batchnbr, doc.entrynbr) for doc in docs)

    # Create string-formatted batch-entry keys for template use
    supported_batch_entries = set(f"{doc.batchnbr}-{doc.entrynbr}" for doc in docs if doc.supported)

    # For backward compatibility, also create batchnbr-only set
    docs_batchnbrs = set(doc.batchnbr for doc in docs)

    # Get all filter parameters
    filters = {
        'period': request.GET.get('filter_period', ''),
        'source': request.GET.get('filter_source', ''),
        'reference': request.GET.get('filter_reference', ''),
        'account': request.GET.get('filter_account', ''),
        'description': request.GET.get('filter_description', ''),
        'posting_sequence': request.GET.get('filter_posting_sequence', ''),
        'date_from': request.GET.get('filter_date_from', ''),
        'date_to': request.GET.get('filter_date_to', ''),
        'amount_from': request.GET.get('filter_amount_from', ''),
        'amount_to': request.GET.get('filter_amount_to', ''),
    }

    # Build Q objects for each filter
    filter_q = Q()

    # Field mapping for database fields
    field_mapping = {
        'period': 'fiscalperd',
        'source': 'drilapp',
        'reference': 'batchnbr',  # Updated to use batchnbr instead of jnldtlref
        'account': 'acctid',
        'description': 'jnldtldesc',
        'posting_sequence': 'postingseq',
    }

    # Apply text-based filters
    for filter_key, filter_value in filters.items():
        if filter_value and filter_key in field_mapping:
            db_field = field_mapping[filter_key]
            if filter_key in ['period', 'posting_sequence']:
                # Exact match for numeric fields
                filter_q &= Q(**{db_field: filter_value})
            else:
                # Partial match for text fields
                filter_q &= Q(**{f"{db_field}__icontains": filter_value})

    # Apply date range filters
    if filters['date_from']:
        try:
            date_from = filters['date_from'].replace('-', '')
            filter_q &= Q(jrnldate__gte=date_from)
        except ValueError:
            pass

    if filters['date_to']:
        try:
            date_to = filters['date_to'].replace('-', '')
            filter_q &= Q(jrnldate__lte=date_to)
        except ValueError:
            pass

    # Apply amount range filters
    if filters['amount_from']:
        try:
            amount_from = float(filters['amount_from'])
            filter_q &= Q(transamt__gte=amount_from)
        except ValueError:
            pass

    if filters['amount_to']:
        try:
            amount_to = float(filters['amount_to'])
            filter_q &= Q(transamt__lte=amount_to)
        except ValueError:
            pass

    # Apply all filters
    if filter_q:
        gl_transactions_list = gl_transactions_list.filter(filter_q)

    # Legacy search functionality (updated to remove jnldtlref)
    search_term = request.GET.get('search', '')
    search_column = request.GET.get('search_column', 'all')

    if search_term:
        if search_column == 'all':
            search_q = (
                    Q(fiscalperd__icontains=search_term) |
                    Q(drilapp__icontains=search_term) |
                    Q(batchnbr__icontains=search_term) |  # Updated from jnldtlref
                    Q(acctid__icontains=search_term) |
                    Q(jnldtldesc__icontains=search_term) |
                    Q(postingseq__icontains=search_term) |
                    Q(jrnldate__icontains=search_term)
            )
            # Add entrynbr to search if it exists in GL transactions
            if hasattr(gl_transactions_list.model, 'entrynbr'):
                search_q |= Q(entrynbr__icontains=search_term)
            gl_transactions_list = gl_transactions_list.filter(search_q)
        else:
            if search_column in field_mapping:
                filter_dict = {f"{field_mapping[search_column]}__icontains": search_term}
                gl_transactions_list = gl_transactions_list.filter(**filter_dict)

    # Apply support filter using composite key matching
    support_filter = request.GET.get('support_filter', 'all')
    if support_filter == 'supported':
        # Create Q objects for composite key matching
        if hasattr(gl_transactions_list.model, 'entrynbr'):
            # If GL transactions have entrynbr, match on both fields
            composite_q = Q()
            for batchnbr, entrynbr in docs_composite_keys:
                composite_q |= Q(batchnbr=batchnbr, entrynbr=entrynbr)
            gl_transactions_list = gl_transactions_list.filter(composite_q)
        else:
            # If GL transactions only have batchnbr, match on that
            gl_transactions_list = gl_transactions_list.filter(batchnbr__in=docs_batchnbrs)

    elif support_filter == 'unsupported':
        if hasattr(gl_transactions_list.model, 'entrynbr'):
            # Exclude transactions that match any composite key
            composite_q = Q()
            for batchnbr, entrynbr in docs_composite_keys:
                composite_q |= Q(batchnbr=batchnbr, entrynbr=entrynbr)
            gl_transactions_list = gl_transactions_list.exclude(composite_q)
        else:
            gl_transactions_list = gl_transactions_list.exclude(batchnbr__in=docs_batchnbrs)

    # Get page number from request
    page = request.GET.get('page', 1)
    items_per_page = 8

    # Set up paginator
    paginator = Paginator(gl_transactions_list, items_per_page)

    try:
        gl_transactions = paginator.page(page)
    except PageNotAnInteger:
        gl_transactions = paginator.page(1)
    except EmptyPage:
        gl_transactions = paginator.page(paginator.num_pages)

    # Calculate statistics
    total_transactions = gl_transactions_list.count()

    # Create docs map for easy lookup using composite key
    docs_map = defaultdict(list)
    for doc in docs:
        # Use tuple as key for composite matching
        composite_key = (doc.batchnbr, doc.entrynbr)
        docs_map[composite_key].append(doc)
        # Also map by batchnbr only for fallback
        docs_map[doc.batchnbr].append(doc)

    docs_with_files = SupportingDocument.objects.filter(
        project=project
    ).prefetch_related(
        Prefetch('documents', queryset=SupportingDocumentFile.objects.all())
    ).select_related('project')

    # Create docs map for easy lookup using composite key
    docs_map = defaultdict(list)
    for doc in docs_with_files:
        # Get all document files for this supporting document
        doc_files = list(doc.documents.all())

        if doc_files:  # Only add if there are actual files
            # Use tuple as key for composite matching
            composite_key = (doc.batchnbr, doc.entrynbr)
            docs_map[composite_key].extend(doc_files)
            # Also map by batchnbr only for fallback
            docs_map[doc.batchnbr].extend(doc_files)

    transactions_with_docs = []

    for transaction in gl_transactions:
        # Try composite key matching first, then fallback to batchnbr only
        transaction_docs = []

        # Check if transaction has entrynbr attribute for composite key matching
        if hasattr(transaction, 'entrynbr'):
            composite_key = (transaction.batchnbr, transaction.entrynbr)
            transaction_docs = docs_map.get(composite_key, [])

        # Fallback to batchnbr matching if no composite match
        if not transaction_docs:
            transaction_docs = docs_map.get(transaction.batchnbr, [])

        transactions_with_docs.append({
            'transaction': transaction,
            'docs': transaction_docs
        })

    # Calculate totals from SupportingDocument model for this project
    project_docs = SupportingDocument.objects.filter(project=project)

    # Calculate supported vs unsupported statistics
    supported_docs = project_docs.filter(supported=True)
    # Simple approach: filter in Python to avoid complex SQL issues
    if docs_composite_keys:
        # Get all current transactions with their composite keys
        current_transactions = gl_transactions_list.values('batchnbr', 'entrynbr', 'acctid', 'fiscalyr', 'fiscalperd',
                                                           'srcecurn', 'srceledger', 'srcetype', 'postingseq',
                                                           'cntdetail')

        # Filter out supported transactions in Python
        unsupported_transaction_keys = []
        supported_keys_set = set(docs_composite_keys)

        for trans in current_transactions:
            trans_key = (trans['batchnbr'], trans['entrynbr'])
            if trans_key not in supported_keys_set:
                # Store the composite primary key for filtering
                unsupported_transaction_keys.append({
                    'acctid': trans['acctid'],
                    'fiscalyr': trans['fiscalyr'],
                    'fiscalperd': trans['fiscalperd'],
                    'srcecurn': trans['srcecurn'],
                    'srceledger': trans['srceledger'],
                    'srcetype': trans['srcetype'],
                    'postingseq': trans['postingseq'],
                    'cntdetail': trans['cntdetail']
                })

        # Create Q objects for the unsupported transactions using their composite primary keys
        if unsupported_transaction_keys:
            unsupported_q = Q()
            for key in unsupported_transaction_keys:
                unsupported_q |= Q(**key)
            unsupported_docs = gl_transactions_list.filter(unsupported_q)
        else:
            unsupported_docs = gl_transactions_list.none()
    else:
        # If no supported documents, all transactions are unsupported
        unsupported_docs = gl_transactions_list

    total_supported_transactions = supported_docs.count()
    total_supported_value = supported_docs.filter(fiscal_year=2025).aggregate(
        total=Sum('transaction_value')
    )['total'] or 0

    total_unsupported_transactions = unsupported_docs.count()
    total_unsupported_value = unsupported_docs.filter(
        transamt__gt=0  # Only positive amounts
    ).aggregate(
        total=Sum('transamt')
    )['total'] or 0

    return JsonResponse({"sucess": True, "data": {
        'transactions': gl_transactions,
        'page_obj': gl_transactions,
        'project_name': project_name,
        'project_id': project.project_id,
        'page_title': 'GL Transactions',
        'total_transactions': total_transactions,
        # Preserve search/filter values for form persistence
        'search_term': search_term,
        'search_column': search_column,
        'support_filter': support_filter,
        'filters': filters,
        'docs_composite_keys': docs_composite_keys,
        'docs_batchnbrs': docs_batchnbrs,  # Keep for fallback
        'transactions_with_docs': transactions_with_docs,
        'total_supported_transactions': total_supported_transactions,
        'total_supported_value': total_supported_value,
        'total_unsupported_transactions': total_unsupported_transactions,
        'total_unsupported_value': total_unsupported_value,
        'comments_dict': comments_dict,
        'supported_batch_entries': supported_batch_entries,  # Add this line
    }}, safe=False)


import os
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.encoding import escape_uri_path
import mimetypes


@require_http_methods(["GET"])
@login_required
def serve_external_file(request, file_path):
    """
    Serve files from Sage 300 external directory.
    """
    # Configure your external files root path (where Sage 300 files are stored)
    external_files_root = r'C:\Sage\Sage300\SharedData'

    print(f"Searching for file: {file_path}")
    print(f"Base path: {external_files_root}")

    # Clean the file path
    clean_file_path = file_path.strip()
    full_path = os.path.join(external_files_root, clean_file_path)

    print(f"Full path: {full_path}")

    # Security check - prevent directory traversal
    normalized_base = os.path.normpath(external_files_root)
    normalized_full = os.path.normpath(full_path)

    if not normalized_full.startswith(normalized_base):
        print(f"Security violation: Path traversal attempt blocked for {file_path}")
        return HttpResponseForbidden("Access denied")

    # Check if file exists
    if os.path.exists(full_path) and os.path.isfile(full_path):
        print(f"File found at: {full_path}")

        try:
            # Get the appropriate content type
            content_type, _ = mimetypes.guess_type(full_path)

            # Create file response for inline viewing
            response = FileResponse(
                open(full_path, 'rb'),
                content_type=content_type,
                filename=os.path.basename(full_path)
            )

            # Set inline header to open in browser/new window instead of downloading
            response['Content-Disposition'] = f'inline; filename="{escape_uri_path(os.path.basename(full_path))}"'

            return response

        except FileNotFoundError:
            print(f"File not found: {full_path}")
            raise Http404("File not found")
        except PermissionError:
            print(f"Permission denied: {full_path}")
            return HttpResponseForbidden("Permission denied")

    else:
        print(f"File '{file_path}' not found in the specified path.")
        print("Checking if the directory exists...")

        # Check parent directory
        parent_dir = os.path.dirname(full_path)

        if os.path.exists(parent_dir):
            print(f"Directory exists: {parent_dir}")
            print("Directory contents:")

            try:
                files = os.listdir(parent_dir)
                for file in files[:10]:  # Show first 10 files
                    file_path_full = os.path.join(parent_dir, file)
                    if os.path.isfile(file_path_full):
                        print(f"  - {file}")
                    else:
                        print(f"  - {file} (directory)")

                if len(files) > 10:
                    print(f"  ... and {len(files) - 10} more items")

            except PermissionError:
                print("Permission denied to list directory contents.")
        else:
            print("The specified directory does not exist.")

        raise Http404("File not found")


def find_document_in_directory(document_name, base_path):
    """
    Helper function to search for a document in the directory structure.
    Similar to your find_document function.
    """
    print(f"Searching for document: {document_name}")
    print(f"Base path: {base_path}")

    if not os.path.exists(base_path):
        print("Base path does not exist.")
        return None

    # Search through directory and subdirectories
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if document_name.lower() in file.lower():
                full_path = os.path.join(root, file)
                print(f"Potential match found: {full_path}")
                return full_path

    return None


@require_http_methods(["GET"])
@login_required
def serve_sage_document(request, document_name):
    """
    Search for and serve a Sage 300 document by name.
    Similar to your main() function logic.
    """
    # Configure base paths for different Sage 300 document types
    base_paths = [
        r'C:\Sage\Sage300\SharedData',
        r'E:\a4w\RM Attachments\tmp_files\INFDAT\EXP',
        # Add more paths as needed
    ]

    print(f"Searching for document: {document_name}")

    # Search in each base path
    for base_path in base_paths:
        print(f"Checking base path: {base_path}")

        if not os.path.exists(base_path):
            print(f"Path does not exist: {base_path}")
            continue

        # Try direct file access first
        potential_files = [
            os.path.join(base_path, document_name),
            os.path.join(base_path, f"{document_name}.pdf"),
            os.path.join(base_path, f"{document_name}.doc"),
            os.path.join(base_path, f"{document_name}.docx"),
        ]

        for file_path in potential_files:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                print(f"Document found at: {file_path}")

                try:
                    # Security check
                    normalized_base = os.path.normpath(base_path)
                    normalized_full = os.path.normpath(file_path)

                    if not normalized_full.startswith(normalized_base):
                        continue

                    # Serve the file for inline viewing
                    content_type, _ = mimetypes.guess_type(file_path)
                    response = FileResponse(
                        open(file_path, 'rb'),
                        content_type=content_type,
                        filename=os.path.basename(file_path)
                    )
                    response[
                        'Content-Disposition'] = f'inline; filename="{escape_uri_path(os.path.basename(file_path))}"'
                    return response

                except (FileNotFoundError, PermissionError) as e:
                    print(f"Error accessing file: {e}")
                    continue

        # If not found directly, search recursively
        found_path = find_document_in_directory(document_name, base_path)
        if found_path:
            try:
                # Security check
                normalized_base = os.path.normpath(base_path)
                normalized_full = os.path.normpath(found_path)

                if normalized_full.startswith(normalized_base):
                    print(f"Document found at: {found_path}")

                    content_type, _ = mimetypes.guess_type(found_path)
                    response = FileResponse(
                        open(found_path, 'rb'),
                        content_type=content_type,
                        filename=os.path.basename(found_path)
                    )
                    response[
                        'Content-Disposition'] = f'inline; filename="{escape_uri_path(os.path.basename(found_path))}"'
                    return response

            except (FileNotFoundError, PermissionError) as e:
                print(f"Error accessing file: {e}")
                continue

        # Show directory contents if document not found in this path
        print(f"Document not found in {base_path}")
        if os.path.exists(base_path):
            try:
                files = os.listdir(base_path)
                print(f"Directory contents ({len(files)} items):")
                for file in files[:10]:
                    print(f"  - {file}")
                if len(files) > 10:
                    print(f"  ... and {len(files) - 10} more files")
            except PermissionError:
                print("Permission denied to list directory contents.")

    # Document not found in any path
    print(f"Document '{document_name}' not found in any of the specified paths.")
    raise Http404("Document not found")


def upload_file(request, batchnbr, entrynbr, project_name):
    if request.method != 'POST':
        return JsonResponse({"response": "invalid method"}, status=405)

    form = UploadFileForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"response": "error", "errors": form.errors}, status=400)

    try:
        project = Project.objects.get(project_name=project_name)
    except Project.DoesNotExist:
        return JsonResponse({"response": "error", "errors": "Project not found"}, status=404)

    try:
        db = DatabaseMapping.objects.get(project_name=project_name)
    except DatabaseMapping.DoesNotExist:
        return JsonResponse({"response": "error", "errors": "Database mapping not found"}, status=404)

    reference = form.cleaned_data.get('reference')
    if not reference:
        return JsonResponse({"response": "error", "errors": "Reference is required"}, status=400)

    # Find the first matching GL transaction (model instance)
    gl_transaction_first = Glpost.objects.using(db.sql_server_db).filter(
        batchnbr=batchnbr,
        entrynbr=entrynbr,
        jnldtlref=reference,
        transamt__gt=0
    ).first()

    if not gl_transaction_first:
        # Strict: do not proceed if no GL transaction found
        return JsonResponse({"response": "error", "errors": "GL transaction not found"}, status=404)

    # Extract fiscal year, period, and reference from the GL transaction (no fallback)
    fiscal_year = str(gl_transaction_first.fiscalyr)
    fiscal_period = str(gl_transaction_first.fiscalperd).zfill(2)
    iddoc = gl_transaction_first.jnldtlref

    # Aggregate sum of transamt for the batch and entry
    transaction_value = Glpost.objects.using(db.sql_server_db).filter(
        batchnbr=batchnbr,
        entrynbr=entrynbr,
        jnldtlref=reference,
        transamt__gt=0
    ).aggregate(total=Sum('transamt'))['total'] or 0

    # Create or get SupportingDocument
    batch_support, created = SupportingDocument.objects.get_or_create(
        project=project,
        batchnbr=batchnbr,
        entrynbr=entrynbr,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        iddoc=iddoc,
        defaults={
            'supported': True,
            'transaction_value': transaction_value,
            'support_count': 1
        }
    )

    if not created:
        # Update existing record's transaction value and supported flag
        batch_support.transaction_value = transaction_value
        batch_support.supported = True
        batch_support.save()

    # Create the SupportingDocumentFile record
    SupportingDocumentFile.objects.create(
        batch_support=batch_support,
        document=form.cleaned_data['file'],
        document_name=form.cleaned_data['file'].name,
        source="User Upload"
    )

    # Update support count correctly (count related documents)
    batch_support.support_count = batch_support.documents.count()
    batch_support.supported = True
    batch_support.save()

    return JsonResponse({"response": "success"})


# If you need a utility function to create combined reference for display purposes
def get_combined_reference(batchnbr, entrynbr):
    """
    Utility function to create a combined reference similar to old jnldtlref
    """
    return f"{batchnbr}-{entrynbr}"


@csrf_protect
@require_POST
def save_transaction_comment(request):
    """
    View to handle saving (create or update) comments via AJAX.
    Updated to handle separate batch and entry numbers if needed
    """
    try:
        # You might need to update this depending on what you're passing from frontend
        transaction_id = request.POST.get('transaction_id')

        batchnbr = transaction_id.strip()[:6]  # Call strip() with ()
        entrynbr = transaction_id.strip()[7:12]  # If passing separately
        comment_text = request.POST.get('comment', '').strip()
        project = request.POST.get('project_name')
        # Handle both cases - combined transaction_id or separate batch/entry numbers
        project = Project.objects.get(project_name=project)
        if not transaction_id and not (batchnbr and entrynbr):
            return JsonResponse({'success': False, 'error': 'Transaction ID or batch/entry numbers are required'})

        # If using combined transaction_id, you might need to split it
        if transaction_id and not (batchnbr and entrynbr):
            # Assuming transaction_id is in format "batchnbrentrynbr" or similar
            # You'll need to adjust this based on your actual format
            if len(transaction_id) >= 7:  # 6 digits batch + at least 1 digit entry
                batchnbr = transaction_id[:6]
                entrynbr = transaction_id[6:]
            else:
                return JsonResponse({'success': False, 'error': 'Invalid transaction ID format'})

        # Create a combined reference for the comment batchid field
        combined_ref = f"{batchnbr}{entrynbr}"

        # Try to get existing comment
        comment_obj = Comments.objects.filter(text=comment_text, user=request.user).first()

        if comment_obj:
            # Update existing comment
            comment_obj.text = comment_text
            comment_obj.save()
            created = False
        else:
            # Create new comment - using combined reference
            comment_obj = Comments.objects.create(
                entrynbr=entrynbr,
                batchnbr=batchnbr,
                user=request.user,
                text=comment_text,
                project=project,
            )
            created = True

        return JsonResponse({
            'success': True,
            'message': 'Comment saved successfully',
            'created': created,
            'comment_id': comment_obj.comments_id
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving comment: {str(e)}")

        return JsonResponse({'success': False, 'error': 'An error occurred while saving the comment'})


def delete_transaction_comment(request):
    """
    This function doesn't directly use jnldtlref, so minimal changes needed
    """
    try:
        comment_id = request.POST.get('comment_id')
        if not comment_id:
            return JsonResponse({'success': False, 'error': 'Comment ID is required'})

        comment = Comments.objects.get(comments_id=comment_id, user=request.user)
        comment.delete()

        return JsonResponse({'success': True, 'message': 'Comment deleted successfully'})

    except Comments.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Comment not found or access denied'})

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting comment: {str(e)}")

        return JsonResponse({'success': False, 'error': 'An error occurred while deleting the comment'})


def delete_transaction_file(request, file_id):
    """
    This function doesn't directly use jnldtlref, so minimal changes needed
    """
    try:
        if not file_id:
            return JsonResponse({'success': False, 'error': 'file is required'})

        file = SupportingDocumentFile.objects.get(doc_file_id=file_id)
        file.delete()

        return JsonResponse({'success': True, 'message': 'File deleted successfully'})

    except SupportingDocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found or access denied'})

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting comment: {str(e)}")

        return JsonResponse({'success': False, 'error': 'An error occurred while deleting the comment'})


def get_transaction_comment_history(request):
    """
    Get comment history for a transaction.
    Updated to handle separate batch and entry numbers
    """
    try:
        # Handle both old and new parameter formats
        transaction_id = request.GET.get('transaction_id')
        batchnbr = transaction_id.strip()[:6] if transaction_id else request.GET.get('batchnbr')
        entrynbr = transaction_id.strip()[7:12] if transaction_id else request.GET.get('entrynbr')

        # Determine the combined reference
        if transaction_id:
            combined_ref = transaction_id
        elif batchnbr and entrynbr:
            combined_ref = f"{batchnbr}-{entrynbr}"
        else:
            return JsonResponse({'success': False, 'error': 'Missing batch ID or transaction parameters'})

        # Get comments for this batch using the combined reference
        comments = Comments.objects.filter(batchnbr=batchnbr, entrynbr=entrynbr)
        print(comments)
        history = []
        for comment in comments:
            user_display = comment.user.get_full_name() or comment.user.username
            # Format the timestamp - use created_at if it exists or current time as fallback
            history.append({
                'id': comment.comments_id,
                'text': comment.text,
                'user': user_display,
                'date': comment.timestamp.strftime('%b %d, %Y, %I:%M %p')
            })

        return JsonResponse({
            'success': True,
            'history': history
        })

    except Exception as e:
        print(f"Error getting comment history: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# Additional view functions you might need for the new model structure

def get_supporting_documents(request, project_name, batchnbr, entrynbr):
    """
    Get supporting documents for a specific batch and entry combination
    """
    try:
        project = Project.objects.get(project_name=project_name)

        supporting_docs = SupportingDocument.objects.filter(
            project=project,
            batchnbr=batchnbr,
            entrynbr=entrynbr
        )

        docs_data = []
        for doc in supporting_docs:
            docs_data.append({
                'id': doc.supporting_docs_id,
                'batchnbr': doc.batchnbr,
                'entrynbr': doc.entrynbr,
                'fiscal_year': doc.fiscal_year,
                'fiscal_period': doc.fiscal_period,
                'supported': doc.supported,
                'transaction_value': str(doc.transaction_value),
                'support_count': doc.support_count,
                'combined_ref': f"{doc.batchnbr}-{doc.entrynbr}"  # For display purposes
            })

        return JsonResponse({
            'success': True,
            'documents': docs_data
        })

    except Project.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Project not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def search_supporting_documents(request, project_name):
    """
    Search supporting documents with separate batch and entry number filtering
    """
    try:
        project = Project.objects.get(project_name=project_name)

        # Get search parameters
        batchnbr = request.GET.get('batchnbr', '').strip()
        entrynbr = request.GET.get('entrynbr', '').strip()
        fiscal_year = request.GET.get('fiscal_year', '').strip()
        fiscal_period = request.GET.get('fiscal_period', '').strip()

        # Build query
        query = SupportingDocument.objects.filter(project=project)

        if batchnbr:
            query = query.filter(batchnbr__icontains=batchnbr)
        if entrynbr:
            query = query.filter(entrynbr__icontains=entrynbr)
        if fiscal_year:
            query = query.filter(fiscal_year=fiscal_year)
        if fiscal_period:
            query = query.filter(fiscal_period=fiscal_period)

        # Execute query and format results
        results = []
        for doc in query[:100]:  # Limit results
            results.append({
                'id': doc.supporting_docs_id,
                'batchnbr': doc.batchnbr,
                'entrynbr': doc.entrynbr,
                'combined_ref': f"{doc.batchnbr}-{doc.entrynbr}",
                'fiscal_year': doc.fiscal_year,
                'fiscal_period': doc.fiscal_period,
                'supported': doc.supported,
                'support_count': doc.support_count,
                'transaction_value': str(doc.transaction_value)
            })

        return JsonResponse({
            'success': True,
            'results': results,
            'count': len(results)
        })

    except Project.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Project not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
