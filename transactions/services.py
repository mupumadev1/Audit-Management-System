import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from main_app.models import *
from transactions.models import *

logger = logging.getLogger(__name__)


class ProjectSyncService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)

    def sync_transactions(self, project_name: None, fiscal_year=None, fiscal_period=None, dry_run=False):
        """
        Sync expense transactions from SQL Server tables to Django models
        """
        db = [project_name.project_name for project_name in DatabaseMapping.objects.filter(is_active=True)]
        projects = Project.objects.filter(project_name__in=db)
        logger.info(f'Found {projects.count()} active projects for syncing')
        synced_count = 0
        if project_name:
            project = projects.get(project_name=project_name)
            sql_server_db = DatabaseMapping.objects.get(project_name=project_name)

            # First, get existing records from supportingdocuments table for this project
            existing_records_query = SupportingDocument.objects.filter(project=project)

            if fiscal_year:
                existing_records_query = existing_records_query.filter(fiscal_year=fiscal_year)
            if fiscal_period:
                existing_records_query = existing_records_query.filter(fiscal_period=fiscal_period.zfill(2))

            # Create a set of (batchnbr, entrynbr) tuples for quick lookup
            existing_records = set(
                existing_records_query.values_list('batchnbr', 'entrynbr')
            )

            logger.info(f'Found {len(existing_records)} existing records for project: {project.project_name}')

            # Build the glpost query
            glpost_query = Glpost.objects.using(sql_server_db.sql_server_db).filter(
                transamt__gt=0,
                srceledger='EN',
                srcetype='EV'
            )

            if fiscal_year:
                glpost_query = glpost_query.filter(fiscalyr=fiscal_year)
            if fiscal_period:
                glpost_query = glpost_query.filter(fiscalperd=fiscal_period.zfill(2))

            # Get all glpost records first, then filter in Python
            # This avoids complex SQL generation issues with ODBC driver
            project_glposts = glpost_query.all()

            # Filter out existing records in Python
            if existing_records:
                filtered_glposts = []
                for glpost in project_glposts:
                    if (glpost.batchnbr, glpost.entrynbr) not in existing_records:
                        filtered_glposts.append(glpost)
                project_glposts = filtered_glposts

            # Get GL posts for this project and filter out existing records
            project_glposts = glpost_query.all()

            # Filter out existing records in Python
            if existing_records:
                filtered_glposts = []
                for glpost in project_glposts:
                    if (glpost.batchnbr, glpost.entrynbr) not in existing_records:
                        filtered_glposts.append(glpost)
                project_glposts = filtered_glposts

            logger.info(f'Processing {len(project_glposts)} new records (after filtering existing)')

            for glpost in project_glposts:
                try:
                    enpjd_records = Enpjd.objects.using(sql_server_db.sql_server_db).filter(iddoc=glpost.jnldtlref)
                    if not enpjd_records.exists():
                        continue

                    # Deduplicate eneba records
                    eneba_records_set = set()
                    eneba_records_list = []

                    for enpjd in enpjd_records:
                        enebas = Eneba.objects.using(sql_server_db.sql_server_db).filter(
                            cntbtch=enpjd.cntbtch,
                            cntitem=enpjd.cntitem
                        )
                        for eneba in enebas:
                            if eneba.id not in eneba_records_set:
                                eneba_records_set.add(eneba.id)
                                eneba_records_list.append(eneba)

                    supporting_doc_data = {
                        'project': project,
                        'batchnbr': glpost.batchnbr,
                        'entrynbr': glpost.entrynbr,
                        'iddoc': glpost.jnldtlref,
                        'fiscal_year': glpost.fiscalyr,
                        'fiscal_period': glpost.fiscalperd,
                        'transaction_value': abs(glpost.transamt),
                        'support_count': 0,  # Initialize to 0, update later
                        'supported': False,
                    }

                    if not dry_run:
                        supporting_doc = SupportingDocument.objects.create(**supporting_doc_data)

                        # Sync attachments
                        self.sync_eneba_attachments(supporting_doc, eneba_records_list)

                        # Update support_count after syncing attachments
                        actual_support_count = supporting_doc.documents.count()  # adjust related_name if needed
                        supporting_doc.support_count = actual_support_count
                        supporting_doc.supported = actual_support_count > 0
                        supporting_doc.save()

                        synced_count += 1
                    else:
                        logger.info(f'Would sync: {supporting_doc_data}')
                        synced_count += 1

                except Exception as e:
                    logger.error(
                       f'Error syncing transaction {glpost.batchnbr}-{glpost.entrynbr}: {str(e)}')

                    continue

        else:
            for project in projects:
                sql_server_db = DatabaseMapping.objects.get(project_name=project.project_name)

                # First, get existing records from supportingdocuments table for this project
                existing_records_query = SupportingDocument.objects.filter(project=project)

                if fiscal_year:
                    existing_records_query = existing_records_query.filter(fiscal_year=fiscal_year)
                if fiscal_period:
                    existing_records_query = existing_records_query.filter(fiscal_period=fiscal_period.zfill(2))

                # Create a set of (batchnbr, entrynbr) tuples for quick lookup
                existing_records = set(
                    existing_records_query.values_list('batchnbr', 'entrynbr')
                )

                logger.info(f'Found {len(existing_records)} existing records for project: {project.project_name}')

                # Build the glpost query
                glpost_query = Glpost.objects.using(sql_server_db.sql_server_db).filter(
                    transamt__gt=0,
                    srceledger='EN',
                    srcetype='EV'
                )

                if fiscal_year:
                    glpost_query = glpost_query.filter(fiscalyr=fiscal_year)
                if fiscal_period:
                    glpost_query = glpost_query.filter(fiscalperd=fiscal_period.zfill(2))

                # Get all glpost records first, then filter in Python
                # This avoids complex SQL generation issues with ODBC driver
                project_glposts = glpost_query.all()

                # Filter out existing records in Python
                if existing_records:
                    filtered_glposts = []
                    for glpost in project_glposts:
                        if (glpost.batchnbr, glpost.entrynbr) not in existing_records:
                            filtered_glposts.append(glpost)
                    project_glposts = filtered_glposts

                # Get GL posts for this project and filter out existing records
                project_glposts = glpost_query.all()

                # Filter out existing records in Python
                if existing_records:
                    filtered_glposts = []
                    for glpost in project_glposts:
                        if (glpost.batchnbr, glpost.entrynbr) not in existing_records:
                            filtered_glposts.append(glpost)
                    project_glposts = filtered_glposts

                logger.info(f'Processing {len(project_glposts)} new records (after filtering existing)')

                for glpost in project_glposts:
                    try:
                        enpjd_records = Enpjd.objects.using(sql_server_db.sql_server_db).filter(iddoc=glpost.jnldtlref)
                        if not enpjd_records.exists():
                            continue

                        # Deduplicate eneba records
                        eneba_records_set = set()
                        eneba_records_list = []

                        for enpjd in enpjd_records:
                            enebas = Eneba.objects.using(sql_server_db.sql_server_db).filter(
                                cntbtch=enpjd.cntbtch,
                                cntitem=enpjd.cntitem
                            )
                            for eneba in enebas:
                                if eneba.id not in eneba_records_set:
                                    eneba_records_set.add(eneba.id)
                                    eneba_records_list.append(eneba)

                        supporting_doc_data = {
                            'project': project,
                            'batchnbr': glpost.batchnbr,
                            'entrynbr': glpost.entrynbr,
                            'iddoc': glpost.jnldtlref,
                            'fiscal_year': glpost.fiscalyr,
                            'fiscal_period': glpost.fiscalperd,
                            'transaction_value': abs(glpost.transamt),
                            'support_count': 0,  # Initialize to 0, update later
                            'supported': False,
                        }

                        if not dry_run:
                            supporting_doc = SupportingDocument.objects.create(**supporting_doc_data)

                            # Sync attachments
                            self.sync_eneba_attachments(supporting_doc, eneba_records_list)

                            # Update support_count after syncing attachments
                            actual_support_count = supporting_doc.documents.count()  # adjust related_name if needed
                            supporting_doc.support_count = actual_support_count
                            supporting_doc.supported = actual_support_count > 0
                            supporting_doc.save()

                            synced_count += 1
                        else:
                            logger.info(f'Would sync: {supporting_doc_data}')
                            synced_count += 1

                    except Exception as e:
                        logger.error(
                         f'Error syncing transaction {glpost.batchnbr}-{glpost.entrynbr}: {str(e)}')

                        continue

        return synced_count

    @staticmethod
    def sync_eneba_attachments(self, supporting_doc, eneba_records):
        """
        Sync attachment information from ENEBA records
        """
        for eneba in eneba_records:
            if eneba.docname and eneba.docpath:
                # Check if this document reference already exists
                existing_doc = SupportingDocumentFile.objects.filter(
                    batch_support=supporting_doc,
                    document_name=eneba.docname,
                    document=eneba.docpath
                ).first()

                if not existing_doc:
                    # Create a placeholder document record
                    # Note: The actual file won't be available, but we track the reference
                    SupportingDocumentFile.objects.create(
                        document=eneba.docpath,
                        batch_support=supporting_doc,
                        document_name=eneba.docname,
                        source='SQL Server Reference',
                        # document field will be empty since we don't have the actual file
                    )
