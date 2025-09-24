from django.core.management import BaseCommand
from django.db.models import Count
from transactions.models import SupportingDocument


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Starting to update supporting document counts...")

        # Call the method to update counts
        self.update_supporting_document_counts()

        self.stdout.write(self.style.SUCCESS("Successfully updated supporting document counts."))

    def update_supporting_document_counts(self):
        # Annotate each SupportingDocument with its related file count
        docs_with_counts = SupportingDocument.objects.annotate(doc_count=Count('documents'))

        # Update the support_count field
        for doc in docs_with_counts:
            if doc.support_count != doc.doc_count:
                doc.support_count = doc.doc_count
                doc.save(update_fields=['support_count'])
