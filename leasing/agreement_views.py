from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods
from common.audit.services import record_event
from .models import Lease
from .agreement_forms import LeaseAgreementForm
from .agreement_pages import page_context

@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def add_agreement(request,lease_id):
    lease=get_object_or_404(Lease.objects.select_related('unit__property'),pk=lease_id)
    form=LeaseAgreementForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            agreement=form.save(commit=False);agreement.lease=lease;agreement.recorded_by=request.user;agreement.save()
            record_event(action='LEASE_AGREEMENT_RECORDED',instance=lease,actor=request.user,request=request,
                old_values={},new_values={'agreement_id':agreement.pk,'title':agreement.title,'kind':agreement.kind,'status':agreement.status},
                reason=form.cleaned_data['change_reason'],property_id=lease.unit.property_id)
        return redirect('portal:lease_detail',lease_id=lease.pk)
    context={'form':form,'lease':lease,'section':'leases','agreement_editable':True}
    context.update(page_context(form))
    return render(request,'portal/lease_agreement_form.html',context)
