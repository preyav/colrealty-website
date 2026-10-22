import csv
from common.models import FormFieldSetting
from .chart_actions import wording as action_wording
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from .models import ChartAccount,FinancialAccount
from .workspace import workspace_ui,settings


def chart_data(params):
    ui=workspace_ui();rows=settings()
    types=rows['chart_account_type'].option_labels
    selected=[key for key in params.getlist('type') if key in types]
    status=params.get('status','active')
    if status not in ('active','inactive','all'):status='active'
    query=params.get('q','').strip()[:200]
    accounts=ChartAccount.objects.all()
    if status!='all':accounts=accounts.filter(is_active=status=='active')
    groups=[{'key':key,'label':label,'count':accounts.filter(account_type=key).count(),'selected':key in selected} for key,label in types.items()]
    if selected:accounts=accounts.filter(account_type__in=selected)
    if query:accounts=accounts.filter(Q(code__icontains=query)|Q(name__icontains=query)|Q(description__icontains=query))
    accounts=list(accounts.select_related('parent').order_by('name','code'))
    fund_row=rows.get('chart_fund_type')
    funds=fund_row.option_labels if fund_row else {}
    for account in accounts:account.display_fund_type=funds.get(account.fund_type,account.fund_type)
    for account in accounts:account.display_type=types.get(account.account_type,account.get_account_type_display())
    columns=[('code',ui['code']),('name',ui['name']),('type',ui['type']),('cash_asset',ui['cash_asset']),('fund_type',ui['fund_type']),('notes',ui['notes']),('status',ui['status'])]
    sort=params.get('sort','name')
    if sort not in dict(columns):sort='name'
    direction=params.get('direction','asc')
    if direction not in ('asc','desc'):direction='asc'
    def key(account):
        if sort=='cash_asset':return account.cash_asset
        if sort=='code':
            import re
            return tuple((0,int(piece)) if piece.isdigit() else (1,piece.casefold()) for piece in re.split(r'(\d+)',account.code) if piece)
        value={'name':account.name,'type':account.display_type,'fund_type':account.display_fund_type,
               'notes':account.description,'status':ui['active'] if account.is_active else ui['inactive']}[sort]
        return value.casefold()
    accounts.sort(key=lambda account:(account.name.casefold(),account.code.casefold(),account.pk))
    accounts.sort(key=key,reverse=direction=='desc')
    headers=[]
    for column,label in columns:
        target=params.copy();target.pop('export',None)
        target['sort']=column;target['direction']='desc' if sort==column and direction=='asc' else 'asc'
        headers.append({'key':column,'label':label,'url':'?'+target.urlencode(),
            'aria':('ascending' if direction=='asc' else 'descending') if sort==column else 'none',
            'indicator':('↑' if direction=='asc' else '↓') if sort==column else '↕'})
    return {'accounts':accounts,'ui':ui,'groups':groups,'status':status,'query':query,'selected_count':len(selected),'count':len(accounts),'headers':headers,'sort':sort,'direction':direction,'show_codes':params.get('show_codes')=='1','account_actions':action_wording()}


@staff_member_required(login_url='/admin/login/')
def accounts(request):
    data=chart_data(request.GET)
    data.update(section='finance',finance_subsection='accounts',banking=request.GET.get('view')=='banking',
        financial_accounts=FinancialAccount.objects.select_related('ledger_account').order_by('name'))
    if data['banking']:
        from .bank_actions import permitted
        row=FormFieldSetting.objects.filter(form_key='bank_account_actions',field_key='ui').first()
        data.update(bank_actions=row.option_labels if row else {},bank_delete_allowed=permitted(request.user,'delete'),bank_change_allowed=permitted(request.user,'inactivate'))
    if request.GET.get('export')=='csv' and not data['banking']:
        response=HttpResponse(content_type='text/csv');response['Content-Disposition']='attachment; filename="chart-of-accounts.csv"'
        writer=csv.writer(response);ui=data['ui']
        writer.writerow([ui['code'],ui['name'],ui['type'],ui['notes'],ui['status']])
        def safe(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        for row in data['accounts']:writer.writerow([safe(row.code),safe(row.name),safe(row.display_type),safe(row.description),ui['active'] if row.is_active else ui['inactive']])
        return response
    return render(request,'portal/finance_accounts.html',data)
