# transactions/services/expense_sync_service.py
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from ..models import SupportingDocument, SupportingDocumentFile, Eneba, Enpjd, Glpost



class ExpenseSyncService:
    """
    Service class to handle synchronization between SQL Server tables and Django models
    """

    @staticmethod
    def get_transaction_summary(project, fiscal_year=None, fiscal_period=None):
        """
        Get summary of transactions for a project
        """
        query = SupportingDocument.objects.filter(project=project)

        if fiscal_year:
            query = query.filter(fiscal_year=fiscal_year)
        if fiscal_period:
            query = query.filter(fiscal_period=fiscal_period)

        return query.aggregate(
            total_transactions=Count('id'),
            total_value=Sum('transaction_value'),
            supported_transactions=Count('id', filter=Q(supported=True)),
            unsupported_transactions=Count('id', filter=Q(supported=False))
        )

    @staticmethod
    def get_unsupported_transactions(project, fiscal_year=None, fiscal_period=None):
        """
        Get transactions that don't have supporting documents
        """
        query = SupportingDocument.objects.filter(
            project=project,
            supported=False
        )

        if fiscal_year:
            query = query.filter(fiscal_year=fiscal_year)
        if fiscal_period:
            query = query.filter(fiscal_period=fiscal_period)

        return query.order_by('-transaction_value')

    @staticmethod
    def sync_single_transaction(batch_nbr, entry_nbr, fiscal_year, fiscal_period, project):
        """
        Sync a single transaction
        """
        try:
            # Find the GL post record
            glpost = Glpost.objects.get(
                batchnbr=batch_nbr,
                entrynbr=entry_nbr,
                fiscalyr=fiscal_year,
                fiscalperd=fiscal_period
            )

            # Find corresponding ENPJD records
            enpjd_records = Enpjd.objects.filter(iddoc=glpost.jnldtlref)

            # Find corresponding ENEBA records
            eneba_records = []
            for enpjd in enpjd_records:
                eneba_records.extend(
                    Eneba.objects.filter(
                        cntbtch=enpjd.cntbtch,
                        cntitem=enpjd.cntitem
                    )
                )

            # Create or update SupportingDocument
            supporting_doc, created = SupportingDocument.objects.get_or_create(
                project=project,
                batchnbr=batch_nbr,
                entrynbr=entry_nbr,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                defaults={
                    'iddoc': glpost.jnldtlref,
                    'transaction_value': abs(glpost.transamt),
                    'support_count': len(eneba_records),
                    'supported': len(eneba_records) > 0,
                }
            )

            return supporting_doc, created

        except Glpost.DoesNotExist:
            raise ValueError(f"GL post not found for batch {batch_nbr}, entry {entry_nbr}")

    @staticmethod
    def update_support_status(supporting_doc):
        """
        Update the support status based on uploaded documents and SQL Server data
        """
        # Count uploaded documents
        uploaded_count = supporting_doc.documents.count()

        # Count SQL Server references
        sql_server_count = supporting_doc.support_count

        # Update status
        supporting_doc.supported = (uploaded_count > 0) or (sql_server_count > 0)
        supporting_doc.save()

        return supporting_doc

    @staticmethod
    def get_transaction_details(supporting_doc):
        """
        Get detailed information about a transaction from all related tables
        """
        details = {
            'supporting_doc': supporting_doc,
            'glpost': None,
            'enpjd_records': [],
            'eneba_records': [],
            'uploaded_documents': supporting_doc.documents.all()
        }

        try:
            # Get GL post record
            details['glpost'] = Glpost.objects.get(
                batchnbr=supporting_doc.batchnbr,
                entrynbr=supporting_doc.entrynbr,
                fiscalyr=supporting_doc.fiscal_year,
                fiscalperd=supporting_doc.fiscal_period
            )

            # Get ENPJD records
            details['enpjd_records'] = Enpjd.objects.filter(
                iddoc=details['glpost'].jnldtlref
            )

            # Get ENEBA records
            for enpjd in details['enpjd_records']:
                details['eneba_records'].extend(
                    Eneba.objects.filter(
                        cntbtch=enpjd.cntbtch,
                        cntitem=enpjd.cntitem
                    )
                )

        except Glpost.DoesNotExist:
            pass

        return details