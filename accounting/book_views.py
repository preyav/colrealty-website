import uuid
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.db import IntegrityError
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from common.models import FormFieldSetting
from .book_models import AccountingEntity,PropertyBooks,BankReconciliation,FundsEvent
from .book_forms import FundsForm,ReconcileForm
from .book_services import post_rent_charge,post_rent_receipt,post_bill,post_bill_payment,record_funds
from .book_reports import operational_balances
from .bank_services import reconcile

def wording():return FormFieldSetting.objects.get(form_key='accounting_books',field_key='ui').option_labels

def source(kind,pk):
    from .rent_models import RentCharge,RentReceipt
    from maintenance.models import VendorInvoice,VendorPayment
    model={'rent-charge':RentCharge,'rent-receipt':RentReceipt,'bill':VendorInvoice,'bill-payment':VendorPayment}.get(kind)
    if model is None:raise ValidationError('Invalid source type.')
    if not str(pk).isdigit():raise ValidationError('Enter a valid source ID.')
    obj=get_object_or_404(model,pk=pk)
    prop=obj.lease.unit.property if kind.startswith('rent-') else (obj.invoice.work_order.unit.property if kind=='bill-payment' else obj.work_order.unit.property)
    return obj,prop

@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def accounting_operations(request):
    entities=AccountingEntity.objects.all()
    entity=get_object_or_404(entities,pk=request.GET['entity']) if request.GET.get('entity') else entities.first()
    ui=wording();error=None;preview=None
    key='accounting_funds_token'
    if request.method=='GET' or key not in request.session:request.session[key]=str(uuid.uuid4())
    action=request.POST.get('action')
    funds=FundsForm(request.POST if action=='funds' else None,entity=entity,initial={'date':timezone.localdate(),'token':request.session[key]})
    bank=ReconcileForm(request.POST if action in ('preview','finalize') else request.GET if request.GET.get('bank') else None,entity=entity)
    if request.method=='POST':
        try:
            if action=='funds' and funds.is_valid():
                data=dict(funds.cleaned_data);token=data.pop('token')
                if str(token)!=request.session[key]:raise ValidationError('Form expired; reload the page.')
                record_funds(data,token,request.user);request.session.pop(key,None)
                messages.success(request,ui['saved']);return redirect(request.get_full_path())
            elif action=='assign-legacy':
                if not entity or request.POST.get('reviewed')!='1':raise ValidationError(ui['review_required'])
                from .book_services import assign_legacy
                assign_legacy(request.POST.get('journal_id'),entity,request.POST.get('basis'),request.user)
                messages.success(request,ui['saved']);return redirect(request.get_full_path())
            elif action=='void-payment':
                obj,prop=source('bill-payment',request.POST.get('source_id'))
                get_object_or_404(PropertyBooks,property=prop,entity=entity,enabled=True)
                from .book_services import void_bill_payment
                void_bill_payment(obj,request.POST.get('reason',''),request.user)
                messages.success(request,ui['saved']);return redirect(request.get_full_path())
            elif action=='post':
                obj,prop=source(request.POST.get('kind'),request.POST.get('source_id'))
                get_object_or_404(PropertyBooks,property=prop,entity=entity,enabled=True)
                if request.POST.get('reviewed')!='1':raise ValidationError(ui['review_required'])
                {'rent-charge':post_rent_charge,'rent-receipt':post_rent_receipt,'bill':post_bill,'bill-payment':post_bill_payment}[request.POST['kind']](obj,request.user)
                messages.success(request,ui['saved']);return redirect(request.get_full_path())
            elif action in ('preview','finalize') and bank.is_valid():
                d=bank.cleaned_data
                preview=reconcile(d['bank'].pk,d['statement_start'],d['statement_end'],d['opening_balance'],d['closing_balance'],[int(x) for x in d['lines']],request.user,finalize=action=='finalize')
                if action=='finalize':messages.success(request,ui['saved']);return redirect(request.get_full_path())
        except ValidationError as exc:error=' '.join(exc.messages)
        except IntegrityError:error=ui['retry']
        except (ObjectDoesNotExist,ValueError):error=ui['missing_record']
    report=operational_balances(entity) if entity else {'tenants':[],'bills':[],'owners':[]}
    pending=[]
    for owner in report['owners']:
        for key in owner['coverage']['missing']:
            kind,pk=key.split(':');obj,prop=source(kind,pk)
            pending.append({'kind':kind,'pk':pk,'label':str(obj),'property':prop})
    return render(request,'portal/accounting_operations.html',{'entities':entities,'entity':entity,'ui':ui,'report':report,'pending':pending,'funds_form':funds,'bank_form':bank,'preview':preview,'error':error,'fund_history':FundsEvent.objects.filter(property__books__entity=entity).select_related('property','lease','bank').order_by('-date','-pk'),'section':'finance','finance_subsection':'operations','reconciliations':BankReconciliation.objects.filter(entity_bank__entity=entity).select_related('entity_bank__bank').order_by('-statement_end')})
