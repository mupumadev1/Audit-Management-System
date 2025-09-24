# templatetags/file_tags.py
from django import template
from django.urls import reverse
import os

register = template.Library()


@register.simple_tag
def get_file_url(doc):
    """Return the appropriate URL based on document source"""
    if doc.source == 'SQL Server Reference':
        # For external files, use the custom view
        return reverse('transactions:serve_external_file', kwargs={'file_path': doc.document.name})
    else:
        # For Django uploads, use the regular document.url
        return doc.document.url