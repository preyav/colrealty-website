"""Tenant-performed work arrangements; saving does not create a bill or rent credit."""
from functools import wraps
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from common.models import FormFieldSetting
from common.audit.services import record_event
from maintenance.models import WorkOrder,WorkOrderStatusHistory,MaintenanceRequest
from tenants.models import TenantProfile
from owners.models import OwnerProfile,PropertyOwnership
from django.db.models import Q


def wording():
    labels=dict(FormFieldSetting.objects.get(form_key='tenant_work',field_key='ui').option_labels)
    assignment=FormFieldSetting.objects.filter(form_key='work_assignment',field_key='ui').first()
    if assignment:labels.update(assignment.option_labels)
    return labels


def eligible_tenants(wo):
    if not wo.maintenance_request_id or not wo.maintenance_request.lease_id:return TenantProfile.objects.none()
    lease=wo.maintenance_request.lease
    if lease.unit_id!=wo.unit_id:return TenantProfile.objects.none()
    return TenantProfile.objects.filter(lease_memberships__lease=lease).distinct()


def eligible_owners(wo):
    today=timezone.localdate()
    ownerships=PropertyOwnership.objects.filter(Q(start_date__isnull=True)|Q(start_date__lte=today),Q(end_date__isnull=True)|Q(end_date__gte=today),property_id=wo.unit.property_id)
    return OwnerProfile.objects.filter(is_active=True,pk__in=ownerships.values('owner_id'))


def snapshot(wo):
    return {'updated':str(wo.updated_at),'status':wo.status,'tenant':wo.performer_tenant_id,'owner':wo.performer_owner_id,'cost':str(wo.estimated_cost),'schedule':str(wo.scheduled_for),'expected_completion':str(wo.tenant_expected_completion),'terms':wo.tenant_work_terms,'document':wo.tenant_work_document}


class TenantWorkForm(forms.Form):
    performer_kind=forms.ChoiceField(choices=[],required=False)
    tenant=forms.ModelChoiceField(queryset=TenantProfile.objects.none(),required=False)
    owner=forms.ModelChoiceField(queryset=OwnerProfile.objects.none(),required=False)
    agreed_cost=forms.DecimalField(max_digits=12,decimal_places=2,min_value=0,required=False)
    terms=forms.CharField(widget=forms.Textarea(attrs={'rows':3}))
    document=forms.URLField(required=False)
    schedule_confirmed=forms.BooleanField(required=False)
    scheduled_for=forms.DateTimeField(required=False,input_formats=['%Y-%m-%dT%H:%M'],widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}))
    expected_completion=forms.DateTimeField(required=False,input_formats=['%Y-%m-%dT%H:%M'],widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}))
    def __init__(self,*args,work_order,**kwargs):
        super().__init__(*args,**kwargs);ui=wording();self.wo=work_order
        self.fields['tenant'].queryset=eligible_tenants(work_order)
        self.fields['owner'].queryset=eligible_owners(work_order)
        self.fields['performer_kind'].choices=[('tenant',ui['tenant_kind']),('owner',ui['owner_kind'])]
        for name,field in self.fields.items():field.label=ui[name];field.help_text=ui.get(name+'_help','')
    def clean(self):
        data=super().clean();ui=wording()
        kind=data.get('performer_kind') or 'tenant'
        data['performer_kind']=kind
        if kind=='owner':
            if not data.get('owner'):self.add_error('owner',ui['owner_required'])
            data['tenant']=None
        else:
            if not data.get('tenant'):self.add_error('tenant',ui['tenant_required'])
            if data.get('agreed_cost') is None:self.add_error('agreed_cost',ui['cost_required'])
            data['owner']=None
        if data.get('schedule_confirmed'):
            start=data.get('scheduled_for');end=data.get('expected_completion')
            if not start:self.add_error('scheduled_for',ui['start_required'])
            if start and start<timezone.now() and start!=self.wo.scheduled_for:self.add_error('scheduled_for',ui['past_date'])
            if end and (not start or end<start):self.add_error('expected_completion',ui['end_order'])
        else:
            data['scheduled_for']=None;data['expected_completion']=None
        return data


@transaction.atomic
def save_arrangement(pk,data,expected,actor,request=None):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('maintenance.change_workorder'):raise PermissionDenied
    ui=wording()
    wo=WorkOrder.objects.select_for_update(of=('self',)).select_related('maintenance_request__lease','unit__property').get(pk=pk)
    if snapshot(wo)!=expected:raise ValidationError(ui['stale'])
    if wo.status not in ('new','approved','assigned','scheduled'):raise ValidationError(ui['locked'])
    if wo.vendor_assignments.exists() or wo.vendor_awards.exists() or wo.vendor_invoices.exists() or wo.vendor_estimates.exists() or wo.quote_requests.exists():raise ValidationError(ui['vendor_conflict'])
    form=TenantWorkForm(data,work_order=wo)
    if not form.is_valid():raise ValidationError([str(e) for errors in form.errors.values() for e in errors])
    values=form.cleaned_data
    mr=MaintenanceRequest.objects.select_for_update().filter(pk=wo.maintenance_request_id).first()
    if mr:
        if not mr.reviewed_at or not mr.reviewed_by_id or mr.status not in ('approved','converted'):raise ValidationError(ui['approval_required'])
    elif not wo.approved_by_id or not wo.approved_at:raise ValidationError(ui['approval_required'])
    old=snapshot(wo);old_status=wo.status
    wo.performer_tenant=values['tenant'];wo.performer_owner=values['owner'];wo.estimated_cost=values['agreed_cost'];wo.tenant_work_terms=values['terms'].strip();wo.tenant_work_document=values['document']
    wo.scheduled_for=values['scheduled_for'];wo.scheduled_until=None;wo.tenant_expected_completion=values['expected_completion']
    wo.status='scheduled' if wo.scheduled_for else 'assigned'
    if mr and wo.approved_by_id is None and wo.approved_at is None:
        wo.approved_by_id=mr.reviewed_by_id;wo.approved_at=mr.reviewed_at
    wo.tenant_arranged_by=actor;wo.tenant_arranged_at=timezone.now()
    wo.save()
    if old_status!=wo.status:WorkOrderStatusHistory.objects.create(work_order=wo,from_status=old_status,to_status=wo.status,changed_by=actor,notes=wo.tenant_work_terms)
    record_event(action='OWNER_WORK_ARRANGED' if wo.performer_owner_id else 'TENANT_WORK_ARRANGED',instance=wo,actor=actor,request=request,old_values=old,new_values={**snapshot(wo),'request_approved_by':mr.reviewed_by_id if mr else None,'request_approved_at':str(mr.reviewed_at) if mr else None,'arranged_by':actor.pk},reason=wo.tenant_work_terms,property_id=wo.unit.property_id)
    return wo


@staff_member_required(login_url='/accounts/login/')
@require_POST
def save_tenant_work(request,work_order_id):
    wo=get_object_or_404(WorkOrder,pk=work_order_id)
    try:
        expected=signing.loads(request.POST.get('version',''),salt='tenant-work',max_age=3600)
        if expected['id']!=wo.pk:raise signing.BadSignature
        save_arrangement(wo.pk,request.POST,expected['values'],request.user,request)
    except (signing.BadSignature,KeyError):messages.error(request,wording()['stale'])
    except ValidationError as exc:messages.error(request,' '.join(exc.messages))
    else:messages.success(request,wording()['saved'])
    return redirect('portal:work_order_detail',work_order_id=wo.pk)


def vendor_work_only(fn):
    @wraps(fn)
    @transaction.atomic
    def wrapped(request,work_order_id,*args,**kwargs):
        # Serialize vendor actions with tenant-arrangement saves on the same work order.
        wo=WorkOrder.objects.select_for_update(of=('self',)).filter(pk=work_order_id).first()
        if wo and wo.is_self_performed:
            messages.error(request,wording()['tenant_not_vendor'])
            return redirect('portal:work_order_detail',work_order_id=work_order_id)
        return fn(request,work_order_id,*args,**kwargs)
    return wrapped
