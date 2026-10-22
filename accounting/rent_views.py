import calendar
import uuid
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from leasing.models import Lease
from leasing.agreement_history import agreement_history
from .rent_forms import ChargeForm,ReceiptForm,ReasonForm
from .rent_services import wording,ledger_data,post_charge,post_receipt,void_entry,apply_credit


def financial_redirect(lease):
    from django.urls import reverse
    return redirect(reverse('portal:lease_detail',args=[lease.pk])+'#lease-financials')


def lease_for(lease_id):
    return get_object_or_404(Lease.objects.select_related('unit__property'),pk=lease_id)


def token_for(request,lease,action):
    key=f'rent_entry:{lease.pk}:{action}'
    if request.method=='GET':request.session[key]=str(uuid.uuid4())
    token=request.session.get(key)
    if not token or request.POST.get('entry_token')!=token:
        if request.method=='POST':raise ValidationError(wording()['expired_form'])
    return token


def entry_defaults(lease, kind, token):
    today=timezone.localdate()
    first=today.replace(day=1)
    last=today.replace(day=calendar.monthrange(today.year,today.month)[1])
    terms=agreement_history(lease,as_of=today)['recorded_terms']
    rent=terms['monthly_rent']
    ledger=ledger_data(lease)
    if kind=='charge':
        # Calendar dates are suggestions; contractual due days remain editable.
        raw=(lease.contract_details or {}).get('rent_due_day')
        try:day=int(raw)
        except (ValueError,TypeError):
            from common.models import FormFieldSetting
            day=int(FormFieldSetting.objects.get(form_key='rent_ledger',field_key='workspace').option_labels['default_due_day'])
        due=first.replace(day=min(day,last.day)) if day and day>0 else first
        return {'period_start':first,'period_end':last,'due_date':due,'amount':rent}
    initial={'received_date':today,'amount':ledger['outstanding'] if ledger['outstanding']>0 else rent,'reference':f'RENT-{token}'}
    previous=lease.rent_receipts.filter(status='recorded').order_by('-received_date','-pk').first()
    if previous:
        initial.update(payment_method=previous.payment_method,financial_account=previous.financial_account_id)
    return initial


def ledger_context(request,lease,bound_kind=None,bound_form=None):
    from common.models import FormFieldSetting
    row=FormFieldSetting.objects.get(form_key='rent_ledger',field_key='workspace')
    context={'lease':lease,'ledger':ledger_data(lease),'ui':wording(),'workspace':row.option_labels,
             'financial_ui':FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui').option_labels,'section':'finance','finance_subsection':'rent','active_kind':bound_kind or request.GET.get('entry','')}
    for kind,Form in [('charge',ChargeForm),('receipt',ReceiptForm)]:
        key=f'rent_entry:{lease.pk}:{kind}'
        token=request.session.get(key)
        if request.method=='GET' and request.session.pop(f'rent_saved:{lease.pk}:{kind}',False):token=None
        if not token:
            token=str(uuid.uuid4());request.session[key]=token
        form=bound_form if kind==bound_kind else Form(initial=entry_defaults(lease,kind,token),auto_id=f'id_{kind}_%s')
        if kind=='receipt' and not form.is_bound:
            method=form.initial.get('payment_method')
            if method not in dict(form.fields['payment_method'].choices):form.initial.pop('payment_method',None)
            account=form.initial.get('financial_account')
            if account and not form.fields['financial_account'].queryset.filter(pk=account).exists():
                form.initial.pop('financial_account',None)

        if kind=='receipt':
            if not form.is_bound and not form.initial.get('financial_account'):
                accounts=list(form.fields['financial_account'].queryset[:2])
                if len(accounts)==1:form.initial['financial_account']=accounts[0].pk
            form.fields['reference'].help_text=context['workspace']['reference_help']
        context[kind+'_form']=form;context[kind+'_token']=token
    return context


@staff_member_required(login_url='/admin/login/')
def rent_ledger(request,lease_id):
    lease=lease_for(lease_id)
    return financial_redirect(lease)


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def rent_entry(request,lease_id,kind):
    lease=lease_for(lease_id);ui=wording();today=timezone.localdate()
    if kind not in ('charge','receipt'):
        from django.http import Http404
        raise Http404
    if request.method=='GET':
        token_for(request,lease,kind)
        context=ledger_context(request,lease)
        return render(request,'portal/lease_financial_entry.html',dict(context,form=context[kind+'_form'],kind=kind,entry_token=context[kind+'_token']))
    try:token=token_for(request,lease,kind)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages));return financial_redirect(lease)
    Form=ChargeForm if kind=='charge' else ReceiptForm
    form=Form(request.POST,auto_id=f'id_{kind}_%s')
    if request.method=='POST' and form.is_valid():
        data=dict(form.cleaned_data)
        link=data.pop('supporting_link','')
        if link:data['notes']='\n'.join(filter(None,[data.get('notes',''),link]))
        try:
            (post_charge if kind=='charge' else post_receipt)(lease.pk,data,uuid.UUID(token),request.user,request)
        except ValidationError as exc:form.add_error(None,exc)
        else:
            request.session[f'rent_saved:{lease.pk}:{kind}']=True
            messages.success(request,ui['saved'])
            if request.POST.get('add_another')=='1':return redirect('portal:rent_entry',lease_id=lease.pk,kind=kind)
            from django.urls import reverse
            return redirect(reverse('portal:lease_detail',args=[lease.pk])+'#lease-financials')
    return render(request,'portal/lease_financial_entry.html',dict(ledger_context(request,lease,kind,form),form=form,kind=kind,entry_token=token))


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def rent_void(request,lease_id,kind,entry_id):
    lease=lease_for(lease_id);ui=wording()
    if kind not in ('charge','receipt'):
        from django.http import Http404
        raise Http404
    entry=get_object_or_404(lease.rent_charges if kind=='charge' else lease.rent_receipts,pk=entry_id)
    form=ReasonForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        try:void_entry(lease.pk,kind,entry.pk,form.cleaned_data['reason'],request.user,request)
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,ui['voided']);return financial_redirect(lease)
    return render(request,'portal/rent_entry.html',{'lease':lease,'form':form,'ui':ui,'kind':'void','entry':entry,'section':'finance','finance_subsection':'rent'})


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['POST'])
def rent_apply_credit(request,lease_id,receipt_id):
    lease=lease_for(lease_id);get_object_or_404(lease.rent_receipts,pk=receipt_id)
    try:apply_credit(lease.pk,receipt_id,request.user,request)
    except ValidationError as exc:messages.error(request,' '.join(exc.messages))
    else:messages.success(request,wording()['credit_applied'])
    return financial_redirect(lease)


@staff_member_required(login_url='/admin/login/')
def rent_overview(request):
    from .rent_services import portfolio_rent_data
    return render(request,'portal/rent_overview.html',{'portfolio':portfolio_rent_data(managed=request.GET.get('managed')=='1'),'ui':wording(),'section':'finance','finance_subsection':'rent'})


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def rent_edit(request, lease_id, kind, entry_id):
    from django import forms
    from django.core import signing
    from django.http import Http404
    from .rent_services import edit_entry, entry_snapshot
    lease = lease_for(lease_id)
    if kind not in ('charge', 'receipt'):
        raise Http404
    entry = get_object_or_404(lease.rent_charges if kind == 'charge' else lease.rent_receipts, pk=entry_id)
    if entry.status == 'void':
        raise Http404
    ui = wording()
    initial = {key: getattr(entry, key) for key in (('period_start','period_end','due_date','amount','notes') if kind == 'charge' else ('received_date','amount','payment_method','reference','financial_account','notes'))}
    if kind=='charge':initial['income_items']=entry.income_items
    Form = ChargeForm if kind == 'charge' else ReceiptForm
    form = Form(request.POST if request.method == 'POST' else None, initial=initial)
    form.fields.pop('supporting_link', None)
    if kind == 'receipt':
        from django.db.models import Q
        from .models import FinancialAccount
        form.fields['financial_account'].queryset = FinancialAccount.objects.filter(Q(pk=entry.financial_account_id) | (Q(is_active=True) & ~Q(kind='credit_card')))
        choices = list(form.fields['payment_method'].choices)
        if entry.payment_method not in dict(choices):
            form.fields['payment_method'].choices = choices + [(entry.payment_method, entry.payment_method)]
    form.fields['reason'] = forms.CharField(label=ReasonForm().fields['reason'].label, widget=forms.Textarea(attrs={'rows':2}))
    stamp = signing.dumps({'lease':lease.pk,'kind':kind,'id':entry.pk,'values':entry_snapshot(entry, kind)}, salt='rent-edit') if request.method == 'GET' else request.POST.get('entry_token','')
    if request.method == 'POST' and form.is_valid():
        try:
            expected = signing.loads(stamp, salt='rent-edit', max_age=3600)
            if (expected['lease'],expected['kind'],expected['id']) != (lease.pk,kind,entry.pk):
                raise signing.BadSignature
            data = dict(form.cleaned_data)
            reason = data.pop('reason')
            edit_entry(lease.pk, kind, entry.pk, data, expected['values'], reason, request.user, request)
        except (signing.BadSignature, KeyError):
            form.add_error(None, ui['edit_stale'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, ui['saved'])
            return financial_redirect(lease)
    return render(request, 'portal/rent_entry.html', {'lease':lease,'entry':entry,'form':form,'ui':ui,'kind':'edit','entry_token':stamp,'section':'finance','finance_subsection':'rent'})
