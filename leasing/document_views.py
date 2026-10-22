"""Staff-only lease attachments, independent of contractual edits."""
import logging
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.validators import URLValidator
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET
from common.audit.services import record_event
from common.document_settings import document_type_setting
from properties.document_uploads import private_document_storage
from .models import Lease, LeaseDocument, LeaseAgreement

logger = logging.getLogger(__name__)

@staff_member_required(login_url='/admin/login/')
@require_POST
def add_document(request, lease_id):
    lease = get_object_or_404(Lease.objects.select_related('unit__property'), pk=lease_id)
    agreement = None
    agreement_id = request.POST.get('agreement_id')
    if agreement_id:
        if not agreement_id.isdigit():
            return JsonResponse({'error':'Invalid agreement.'}, status=400)
        agreement = get_object_or_404(LeaseAgreement, pk=agreement_id, lease=lease)
    category = request.POST.get('category', 'other')
    if category not in dict(LeaseDocument.CATEGORY_CHOICES):
        return JsonResponse({'error':'Choose a valid document category.'}, status=400)
    type_setting = document_type_setting()
    uploaded = request.FILES.get('file')
    url = request.POST.get('url', '').strip()
    if bool(uploaded) == bool(url):
        return JsonResponse({'error':'Upload one file or paste one link.'}, status=400)
    title = request.POST.get('title', '').strip()[:255]
    filename = ''
    storage = None
    key = ''
    if uploaded:
        limit = settings.PROPERTY_DOCUMENT_MAX_UPLOAD_BYTES
        filename = Path(uploaded.name.replace('\\', '/')).name[:255]
        extension = Path(filename).suffix.lower()
        if not uploaded.size or uploaded.size > limit:
            return JsonResponse({'error':f'Choose a nonempty file smaller than {limit // (1024*1024)} MB.'}, status=400)
        if extension not in settings.PROPERTY_DOCUMENT_ALLOWED_EXTENSIONS:
            return JsonResponse({'error':'This file type is not supported.'}, status=400)
        try:
            storage = private_document_storage()
        except (ImproperlyConfigured, KeyError):
            return JsonResponse({'error':'Private document storage is unavailable.'}, status=503)
        title = title or filename
    else:
        try:
            URLValidator(schemes=['http','https'])(url)
            if len(url) > 2000:
                raise ValidationError('Link too long')
        except ValidationError:
            return JsonResponse({'error':'Enter a valid http or https link.'}, status=400)
        title = title or 'Document link'
    try:
        if uploaded:
            key = storage.save('lease-documents/' + uuid4().hex + extension, uploaded)
        with transaction.atomic():
            document = LeaseDocument.objects.create(lease=lease, agreement=agreement, title=title, category=category,
                url=url, storage_key=key, original_name=filename, uploaded_by=request.user)
            record_event(action='LEASE_DOCUMENT_ADDED', instance=lease, actor=request.user,
                request=request, old_values={}, new_values={'document_id':document.pk,'title':title,'category':category,'agreement_id':agreement.pk if agreement else None},
                reason='Lease supporting document added.', property_id=lease.unit.property_id)
    except Exception:
        if key:
            try:
                storage.delete(key)
            except Exception:
                logger.exception('Failed lease attachment cleanup')
        logger.exception('Lease document save failed')
        return JsonResponse({'error':'The document could not be saved. Please try again.'}, status=503)
    link = url or reverse('portal:lease_document_download', kwargs={'lease_id':lease.pk,'document_id':document.pk}) + '?view=1'
    return JsonResponse({'document_id':document.pk,'delete_url':reverse('portal:lease_document_delete',args=[lease.pk,document.pk]),'title':title,'category':type_setting.option_labels.get(document.category, document.get_category_display()),'url':link}, status=201)

@staff_member_required(login_url='/admin/login/')
@require_GET
def download_document(request, lease_id, document_id):
    document = get_object_or_404(LeaseDocument, pk=document_id, lease_id=lease_id)
    if not document.storage_key:
        raise Http404
    try:
        handle = private_document_storage().open(document.storage_key, 'rb')
    except FileNotFoundError as exc:
        raise Http404 from exc
    inline_pdf = request.GET.get('view') == '1' and document.original_name.lower().endswith('.pdf')
    response = FileResponse(handle, as_attachment=not inline_pdf, filename=document.original_name,
                            content_type='application/pdf' if inline_pdf else 'application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
