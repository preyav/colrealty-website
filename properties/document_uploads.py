"""Private property uploads; public listing storage is never used."""
import logging
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import storages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .models import Property, PropertyDocumentUpload

logger = logging.getLogger(__name__)


def private_document_storage():
    # A missing private backend must never fall back to public media storage.
    return storages['property_documents']


@staff_member_required(login_url='/admin/login/')
@require_POST
def upload_property_document(request):
    uploaded = request.FILES.get('file')
    if uploaded is None:
        return JsonResponse({'error': 'Choose a document to upload.'}, status=400)
    limit = settings.PROPERTY_DOCUMENT_MAX_UPLOAD_BYTES
    if uploaded.size == 0 or uploaded.size > limit:
        return JsonResponse({'error': f'Choose a nonempty document smaller than {limit // (1024 * 1024)} MB.'}, status=400)
    filename = Path(uploaded.name.replace('\\', '/')).name[:255]
    extension = Path(filename).suffix.lower()
    if extension not in settings.PROPERTY_DOCUMENT_ALLOWED_EXTENSIONS:
        return JsonResponse({'error': 'This file type is not supported.'}, status=400)
    property_obj = None
    property_id = request.POST.get('property_id')
    if property_id:
        property_obj = get_object_or_404(Property, pk=property_id)
    try:
        storage = private_document_storage()
    except (ImproperlyConfigured, KeyError):
        return JsonResponse({'error': 'Private document storage has not been configured.'}, status=503)
    key = None
    try:
        key = storage.save(f'{uuid4().hex}{extension}', uploaded)
        document = PropertyDocumentUpload.objects.create(
            property=None, uploaded_by=request.user,
            storage_key=key, original_name=filename,
        )
    except Exception:
        if key:
            try:
                storage.delete(key)
            except Exception:
                logger.exception('Could not remove failed property upload')
        logger.exception('Property document upload failed')
        return JsonResponse({'error': 'The document could not be uploaded. Please try again.'}, status=503)
    return JsonResponse({
        'url': request.build_absolute_uri(reverse('portal:property_document_download', kwargs={'upload_id': document.pk})),
        'title': Path(filename).stem[:255],
        'filename': filename,
    }, status=201)


@staff_member_required(login_url='/admin/login/')
@require_GET
def download_property_document(request, upload_id):
    document = get_object_or_404(PropertyDocumentUpload, pk=upload_id)
    # Unattached uploads remain private to the staff member who uploaded them.
    if document.property_id is None and document.uploaded_by_id != request.user.pk:
        raise Http404
    try:
        handle = private_document_storage().open(document.storage_key, 'rb')
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(handle, as_attachment=True, filename=document.original_name, content_type='application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
