from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
from common.audit.services import record_event
from common.models import FormFieldSetting
from .models import Lease, LeaseAgreement
from .agreement_forms import LeaseAgreementForm


GROUPS = [
    ('identity', ['kind', 'title', 'status', 'named_landlords', 'named_tenants']),
    ('dates', ['effective_date', 'signed_date', 'expiration_date']),
    ('rent', ['rent_action', 'monthly_rent']),
    ('contact', ['contact_action', 'contact_details']),
    ('amendments', ['paragraph_references', 'amendment_text']),
    ('conditional', ['return_deadline', 'unsigned_outcome', 'unsigned_rent', 'unsigned_effective_date']),
    ('review', ['signature_details', 'review_notes', 'change_reason']),
]


def page_context(form, agreement=None):
    ui = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key='lease_agreement_page')}
    groups = [{'key': key, 'label': ui[key].label, 'fields': [form[name] for name in names if name in form.fields]} for key, names in GROUPS]
    return {'agreement_groups': groups, 'agreement_ui': ui, 'agreement': agreement}


def snapshot(agreement):
    return {field.name: str(getattr(agreement, field.name)) if getattr(agreement, field.name) is not None else None
            for field in LeaseAgreement._meta.fields if field.name not in ('id', 'lease', 'recorded_by', 'created_at')}


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET', 'POST'])
def agreement_detail(request, lease_id, agreement_id):
    lease = get_object_or_404(Lease.objects.select_related('unit__property'), pk=lease_id)
    agreement = get_object_or_404(LeaseAgreement, pk=agreement_id, lease=lease)
    editable = agreement.status == 'draft'
    if request.method == 'POST':
        with transaction.atomic():
            agreement = get_object_or_404(LeaseAgreement.objects.select_for_update(), pk=agreement_id, lease=lease)
            if agreement.status != 'draft':
                return HttpResponseNotAllowed(['GET'])
            before = snapshot(agreement)
            form = LeaseAgreementForm(request.POST, instance=agreement)
            if form.is_valid():
                form.save()
                record_event(action='LEASE_AGREEMENT_UPDATED', instance=lease, actor=request.user,
                             request=request, old_values=before, new_values=snapshot(agreement),
                             reason=form.cleaned_data['change_reason'], property_id=lease.unit.property_id)
                return redirect('portal:lease_agreement_detail', lease_id=lease.pk, agreement_id=agreement.pk)
    else:
        form = LeaseAgreementForm(instance=agreement)
        if not editable:
            form.fields.pop('change_reason')
            for field in form.fields.values():
                field.disabled = True
    context = {'form': form, 'lease': lease, 'section': 'leases', 'agreement_editable': editable}
    context.update(page_context(form, agreement))
    return render(request, 'portal/lease_agreement_form.html', context)
