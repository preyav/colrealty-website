"""Reviewed, atomic replacement of unposted lease allocations."""
from decimal import Decimal, InvalidOperation
from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.db import transaction
from common.models import FormFieldSetting
from .rent_models import RentAllocation
from .rent_services import _staff, _lock, audit, entry_snapshot
from .rent_views import lease_for, financial_redirect


def labels():
    return FormFieldSetting.objects.get(form_key='rent_allocations',field_key='ui').option_labels


def snapshot(lease):
    return {
        'charges': [[x.pk,entry_snapshot(x,'charge')] for x in lease.rent_charges.order_by('pk')],
        'receipts': [[x.pk,entry_snapshot(x,'receipt')] for x in lease.rent_receipts.order_by('pk')],
        'allocations': [[x.pk,x.receipt_id,x.charge_id,str(x.amount)] for x in RentAllocation.objects.filter(receipt__lease=lease).order_by('pk')],
    }


@transaction.atomic
def replace_allocations(lease_id, values, expected, reason, actor, request=None):
    _staff(actor)
    if not actor.has_perm('accounting.change_rentallocation'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    lease=_lock(lease_id);ui=labels()
    if snapshot(lease)!=expected:raise ValidationError(ui['stale'])
    if not reason.strip():raise ValidationError(ui['reason_required'])
    from .book_models import FundsEvent
    from .journal_models import JournalEntry
    # Changing existing accounting allocations requires reversal/reposting, not mutation.
    if JournalEntry.objects.filter(property_id=lease.unit.property_id).exists() or FundsEvent.objects.filter(lease=lease).exists():
        raise ValidationError(ui['locked'])
    charges={x.pk:x for x in lease.rent_charges.filter(status='posted')}
    receipts={x.pk:x for x in lease.rent_receipts.filter(status='recorded')}
    normalized={};ct={};rt={}
    for (rid,cid),raw in values.items():
        try:amount=Decimal(str(raw) or '0')
        except InvalidOperation:raise ValidationError(ui['invalid'])
        if not amount.is_finite() or amount<0 or amount!=amount.quantize(Decimal('.01')):raise ValidationError(ui['invalid'])
        if rid not in receipts or cid not in charges:raise ValidationError(ui['invalid'])
        if not amount:continue
        normalized[(rid,cid)]=amount
        ct[cid]=ct.get(cid,Decimal('0'))+amount;rt[rid]=rt.get(rid,Decimal('0'))+amount
    if any(v>charges[k].amount for k,v in ct.items()) or any(v>receipts[k].amount for k,v in rt.items()):raise ValidationError(ui['overallocated'])
    old=list(RentAllocation.objects.filter(receipt_id__in=receipts).values('id','receipt_id','charge_id','amount'))
    current={(a['receipt_id'],a['charge_id']):a for a in old}
    for key,row in current.items():
        if key not in normalized:RentAllocation.objects.filter(pk=row['id']).delete()
    for (rid,cid),amount in normalized.items():
        RentAllocation.objects.update_or_create(receipt_id=rid,charge_id=cid,defaults={'amount':amount})
    new=list(RentAllocation.objects.filter(receipt_id__in=receipts).values('id','receipt_id','charge_id','amount'))
    # Voided receipt allocations remain untouched. Their original rows are historical evidence.
    if old!=new:
        audit('RENT_ALLOCATIONS_CORRECTED',next(iter(receipts.values())),actor,request,
              old={'allocations':[{**r,'amount':str(r['amount'])} for r in old]},new={'allocations':[{**r,'amount':str(r['amount'])} for r in new]},reason=reason.strip())


@staff_member_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def rent_allocations(request,lease_id):
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perm('accounting.change_rentallocation'):raise PermissionDenied
    lease=lease_for(lease_id);ui=labels()
    charges=list(lease.rent_charges.filter(status='posted').order_by('period_start','pk'))
    receipts=list(lease.rent_receipts.filter(status='recorded').order_by('received_date','pk'))
    fields={'reason':forms.CharField(label=ui['reason'],widget=forms.Textarea(attrs={'rows':2}))}
    existing={(a.receipt_id,a.charge_id):a.amount for a in RentAllocation.objects.filter(receipt__lease=lease,receipt__status='recorded')}
    initial={};rows=[]
    for receipt in receipts:
        names=[]
        for charge in charges:
            name=f'a_{receipt.pk}_{charge.pk}'
            fields[name]=forms.DecimalField(label=f'{charge.period_start:%m/%d/%Y} – {charge.period_end:%m/%d/%Y}',required=False,min_value=0,max_digits=12,decimal_places=2,widget=forms.NumberInput(attrs={'step':'.01'}))
            initial[name]=existing.get((receipt.pk,charge.pk),0);names.append(name)
        rows.append((receipt,names))
    Form=type('AllocationForm',(forms.Form,),fields)
    form=Form(request.POST if request.method=='POST' else None,initial=initial)
    stamp=request.POST.get('entry_token','') if request.method=='POST' else signing.dumps({'lease':lease.pk,'values':snapshot(lease)},salt='rent-allocations')
    if request.method=='POST' and form.is_valid():
        try:
            expected=signing.loads(stamp,salt='rent-allocations',max_age=3600)
            if expected['lease']!=lease.pk:raise signing.BadSignature
            values={(r.pk,c.pk):form.cleaned_data[f'a_{r.pk}_{c.pk}'] or 0 for r in receipts for c in charges}
            replace_allocations(lease.pk,values,expected['values'],form.cleaned_data['reason'],request.user,request)
        except (signing.BadSignature,KeyError):form.add_error(None,ui['stale'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,ui['saved']);return financial_redirect(lease)
    return render(request,'portal/rent_allocations.html',{'lease':lease,'ui':ui,'form':form,'entry_token':stamp,'rows':[{'receipt':r,'fields':[form[n] for n in ns]} for r,ns in rows]})
