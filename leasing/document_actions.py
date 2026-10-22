from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from common.audit.services import record_event
from .models import LeaseDocument


@staff_member_required(login_url='/admin/login/')
@require_POST
def delete_document(request, lease_id, document_id):
    with transaction.atomic():
        document = get_object_or_404(LeaseDocument.objects.select_for_update().select_related('lease__unit'),pk=document_id,lease_id=lease_id)
        supplied = request.POST.get('agreement_id', '')
        if supplied != (str(document.agreement_id) if document.agreement_id else ''):
            raise Http404
        lease = document.lease
        old = {'document_id':document.pk,'agreement_id':document.agreement_id,'category':document.category,
               'title':document.title,'url':document.url,'storage_key':document.storage_key,'original_name':document.original_name}
        record_event(action='LEASE_DOCUMENT_REMOVED',instance=lease,actor=request.user,request=request,
                     old_values=old,new_values={},reason='Supporting document entry removed from COL360.',property_id=lease.unit.property_id)
        document.delete()
    # Original Drive/private files are preserved; no external delete is performed.
    return JsonResponse({'deleted':document_id})
