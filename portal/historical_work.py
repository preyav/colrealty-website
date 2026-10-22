"""Record actual completion without inventing a scheduling history."""
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from common.models import FormFieldSetting
from common.audit.services import record_event
from maintenance.models import WorkOrder,WorkOrderStatusHistory
from .tenant_work import wording as tenant_work_wording


def wording():
    return FormFieldSetting.objects.get(form_key='work_completion',field_key='ui').option_labels


def snapshot(wo):
    return {'status':wo.status,'updated':str(wo.updated_at),'started':str(wo.started_at),
            'tenant':wo.performer_tenant_id,'owner':wo.performer_owner_id,'tenant_cost':str(wo.estimated_cost),
            'assignments':list(wo.vendor_assignments.order_by('pk').values_list('pk','vendor_id','status')),
            'awards':list(wo.vendor_awards.order_by('pk').values_list('pk','vendor_id','status'))}


def canonical(value):
    import json
    return json.loads(json.dumps(value))


@transaction.atomic
def record_completion(pk,when,cost,notes,expected,actor,request=None):
    ui=wording()
    if not actor.is_active or not actor.is_staff or not actor.has_perm('maintenance.change_workorder'):raise PermissionDenied
    wo=WorkOrder.objects.select_for_update().select_related('unit__property').get(pk=pk)
    if canonical(snapshot(wo))!=expected:raise ValidationError(ui['stale'])
    if wo.status not in ('assigned','scheduled','in_progress'):raise ValidationError(ui['invalid_status'])
    if when is None or when>timezone.now() or (wo.started_at and when<wo.started_at):raise ValidationError(ui['invalid_date'])
    if not notes.strip():raise ValidationError(ui['notes_required'])
    if cost is not None and (not cost.is_finite() or cost<0 or cost!=cost.quantize(__import__('decimal').Decimal('.01'))):raise ValidationError(ui['invalid_cost'])
    award=wo.vendor_awards.filter(status='active').first()
    assignments=wo.vendor_assignments.filter(status__in=['assigned','accepted','scheduled','in_progress'])
    if award:assignments=assignments.filter(vendor_id=award.vendor_id)
    assignments=list(assignments)
    if wo.is_self_performed:
        if assignments or award or wo.vendor_invoices.exists():raise ValidationError(ui['vendor_required'])
        if wo.performer_tenant_id and (cost is None or (wo.estimated_cost is not None and cost>wo.estimated_cost)):raise ValidationError(tenant_work_wording()['actual_cost_required'])
    elif len(assignments)!=1:raise ValidationError(ui['vendor_required'])
    old={'status':wo.status,'completed_at':wo.completed_at,'actual_cost':wo.actual_cost}
    previous=wo.status
    wo.status='completed';wo.completed_at=when;wo.actual_cost=cost
    wo.notes='\n\n'.join(filter(None,[wo.notes,notes.strip()]))
    wo.save(update_fields=['status','completed_at','actual_cost','notes','updated_at'])
    assignment=assignments[0] if assignments else None
    if assignment:
        assignment.status='completed';assignment.completed_at=when
        assignment.save(update_fields=['status','completed_at','updated_at'])
    if wo.maintenance_request_id:
        mr=wo.maintenance_request.__class__.objects.select_for_update().get(pk=wo.maintenance_request_id)
        # A shared request stays open while another noncancelled work order remains open.
        if not WorkOrder.objects.filter(maintenance_request=mr).exclude(status__in=['completed','cancelled']).exists():
            old_status=mr.status;mr.status='completed';mr.save(update_fields=['status','updated_at'])
            record_event(action='MAINTENANCE_REQUEST_COMPLETED',instance=mr,actor=actor,request=request,old_values={'status':old_status},new_values={'status':mr.status},reason=notes.strip(),property_id=wo.unit.property_id)
    WorkOrderStatusHistory.objects.create(work_order=wo,from_status=previous,to_status='completed',changed_by=actor,notes=notes.strip())
    record_event(action='WORK_ORDER_COMPLETED',instance=wo,actor=actor,request=request,old_values=old,new_values={'status':wo.status,'completed_at':when,'actual_cost':cost,'assignment_id':assignment.pk if assignment else None,'performer_tenant_id':wo.performer_tenant_id,'performer_owner_id':wo.performer_owner_id,'entry_mode':'record_actual_completion'},reason=notes.strip(),property_id=wo.unit.property_id)
    return wo


@staff_member_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def record_work_completion(request,work_order_id):
    if not request.user.has_perm('maintenance.change_workorder'):raise PermissionDenied
    wo=get_object_or_404(WorkOrder.objects.select_related('unit__property'),pk=work_order_id);ui=wording()
    Form=type('CompletionForm',(forms.Form,),{
        'completed_at':forms.DateTimeField(label=ui['date'],input_formats=['%Y-%m-%dT%H:%M'],widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}),help_text=ui['date_help']),
        'actual_cost':forms.DecimalField(label=ui['cost'],required=False,min_value=0,max_digits=12,decimal_places=2,help_text=ui['cost_help']),
        'notes':forms.CharField(label=ui['notes'],widget=forms.Textarea(attrs={'rows':3}),help_text=ui['notes_help'])})
    form=Form(request.POST if request.method=='POST' else None,initial={'actual_cost':wo.actual_cost})
    stamp=request.POST.get('version','') if request.method=='POST' else signing.dumps({'id':wo.pk,'values':canonical(snapshot(wo))},salt='work-completion')
    if request.method=='POST' and form.is_valid():
        try:
            expected=signing.loads(stamp,salt='work-completion',max_age=3600)
            if expected['id']!=wo.pk:raise signing.BadSignature
            record_completion(wo.pk,form.cleaned_data['completed_at'],form.cleaned_data['actual_cost'],form.cleaned_data['notes'],expected['values'],request.user,request)
        except (signing.BadSignature,KeyError):form.add_error(None,ui['stale'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,ui['saved']);return redirect('portal:work_order_detail',work_order_id=wo.pk)
    return render(request,'portal/record_work_completion.html',{'work_order':wo,'ui':ui,'form':form,'version':stamp,'section':'maintenance'})
