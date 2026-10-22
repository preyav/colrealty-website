import csv
import uuid
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .general_ledger import wording,funds,ledger_report,post_journal,reverse_journal
from .journal_forms import LedgerFilter,JournalForm,JournalLines,ReverseForm
from .journal_models import JournalEntry


def common():return {'today':timezone.localdate(),'ui':wording(),'section':'finance','finance_subsection':'general_ledger'}


def token(request,key):
    if request.method=='GET' or key not in request.session:request.session[key]=str(uuid.uuid4())
    return request.session[key]


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET'])
def general_ledger(request):
    today=timezone.localdate();data=request.GET.copy()
    if not data:data.update({'date_range':'last30','start':(today-timedelta(days=29)).isoformat(),'end':today.isoformat()})
    if not data.get('scope'):data['scope']='properties'
    preset=data.get('date_range','custom')
    if preset in ('month','year','last30'):
        start=today.replace(day=1) if preset=='month' else (today.replace(month=1,day=1) if preset=='year' else today-timedelta(days=29))
        data['start']=start.isoformat();data['end']=today.isoformat()
    from .book_models import AccountingEntity
    entity=AccountingEntity.objects.filter(pk=data.get('entity')).first() if data.get('entity','').isdigit() else AccountingEntity.objects.filter(is_active=True).first()
    if entity:data.setdefault('entity',str(entity.pk));data.setdefault('basis',entity.default_basis)
    form=LedgerFilter(data);report=ledger_report(form.cleaned_data) if form.is_valid() else None
    context={**common(),'form':form,'report':report}
    if report is not None and request.GET.get('export')=='csv':
        response=HttpResponse(content_type='text/csv');response['Content-Disposition']='attachment; filename="general-ledger.csv"';writer=csv.writer(response);ui=wording()
        writer.writerow([ui['account'],ui['date'],ui['journal'],ui['property'],ui['unit'],ui['fund_type'],ui['memo'],ui['debit'],ui['credit'],ui['balance']])
        def safe(value):
            value=str(value);return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        for group in report['groups']:
            writer.writerow([safe(group['account']), '', '', '', '', '',ui['opening'],0,0,group['opening']])
            for row in group['rows']:
                line=row['line'];j=line.journal
                writer.writerow([safe(line.account),j.date,j.pk,safe(j.property or ui['company']),safe(j.unit or ''),safe(j.display_fund_type),safe(j.memo),line.debit,line.credit,row['balance']])
        return response
    return render(request,'portal/general_ledger.html',context)


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def journal_create(request):
    ui=wording();key='journal_entry_token';entry_token=token(request,key);error=None
    form=JournalForm(request.POST if request.method=='POST' else None,initial={'date':timezone.localdate()})
    lines=JournalLines(request.POST if request.method=='POST' else None,prefix='lines')
    if request.method=='POST' and form.is_valid() and lines.is_valid():
        if request.POST.get('entry_token')!=entry_token:error=ui['expired']
        else:
            try:
                journal=post_journal(form.cleaned_data,[line.cleaned_data for line in lines if line.cleaned_data],uuid.UUID(entry_token),request.user,request)
            except ValidationError as exc:error=' '.join(exc.messages)
            except IntegrityError:error=ui['retry']
            else:return redirect('portal:journal_detail',journal_id=journal.pk)
    return render(request,'portal/journal_form.html',{**common(),'form':form,'lines':lines,'entry_token':entry_token,'error':error})


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def journal_detail(request,journal_id):
    journal=get_object_or_404(JournalEntry.objects.select_related('property','unit','created_by').prefetch_related('lines__account'),pk=journal_id)
    ui=wording();key='journal_reverse:'+str(journal.pk);entry_token=token(request,key);error=None
    form=ReverseForm(request.POST if request.method=='POST' else None,initial={'date':timezone.localdate()})
    if request.method=='POST' and form.is_valid():
        if request.POST.get('entry_token')!=entry_token:error=ui['expired']
        else:
            try:result=reverse_journal(journal.pk,form.cleaned_data['date'],form.cleaned_data['memo'],uuid.UUID(entry_token),request.user,request)
            except ValidationError as exc:error=' '.join(exc.messages)
            except IntegrityError:error=ui['retry']
            else:return redirect('portal:journal_detail',journal_id=result.pk)
    return render(request,'portal/journal_detail.html',{**common(),'journal':journal,'fund_label':funds().get(journal.fund_type,journal.fund_type or ui['unknown']),'form':form,'entry_token':entry_token,'error':error,'can_reverse':not journal.reversal_of_id and not hasattr(journal,'reversal')})
