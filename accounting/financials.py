"""Property income and expenses from posted COL360 journal entries."""
from decimal import Decimal
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from common.models import FormFieldSetting
from properties.models import Property
from .models import ChartAccount
from .journal_forms import LedgerFilter
from .general_ledger import ledger_report,wording

ZERO=Decimal('0.00')


def labels():
    return FormFieldSetting.objects.get(form_key='financials',field_key='ui').option_labels


def month_start(date,offset):
    index=date.year*12+date.month-1+offset
    return date.replace(year=index//12,month=index%12+1,day=1)


class FinancialFilter(LedgerFilter):
    period=forms.ChoiceField(choices=[])
    show_empty=forms.BooleanField(required=False)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for key in ('accounts','fund_type','date_range','start','end'):self.fields.pop(key)
        ui=labels()
        self.fields['period'].choices=[(key,ui[key]) for key in ('three','six','twelve','year','month')]
        self.fields['period'].label=ui['period']
        self.fields['show_empty'].label=ui['show_empty']
        self.order_fields(['entity','scope','unit','period','basis','show_empty'])


def financial_report(cleaned,today):
    period=cleaned['period']
    start=month_start(today,-{'three':2,'six':5,'twelve':11,'year':today.month-1,'month':0}[period])
    months=[];cursor=start
    while cursor<=today:
        months.append(cursor);cursor=month_start(cursor,1)
    properties=Property.objects.all()
    if cleaned.get('entity'):properties=properties.filter(books__entity=cleaned['entity'])
    if cleaned.get('property'):properties=properties.filter(pk=cleaned['property'].pk)
    ui=labels()
    configured={r.field_key:r.option_labels.get('classification') for r in FormFieldSetting.objects.filter(form_key='financial_account_classification')}
    chart=list(ChartAccount.objects.filter(account_type__in=['income','expense']).order_by('code','name','pk'))
    result=[]
    for prop in properties:
        report=ledger_report({**cleaned,'scope':'property','property':prop,'start':start,'end':today})
        groups={g['account'].pk:g for g in report['groups']}
        # Use the actual relation declared on PropertyUnit, including inactive units with history.
        from properties.models import PropertyUnit
        units=list(PropertyUnit.objects.filter(property=prop).order_by('unit_number','pk'))
        unit_count=len(units)
        if cleaned.get('unit_all') is False:
            units=[u for u in units if cleaned.get('unit_all_units') or str(u.pk) in [str(x) for x in cleaned.get('unit_ids',[])]]
        include_property=cleaned.get('unit_all') is not False or cleaned.get('unit_property_level')
        single=unit_count==1 and not prop.is_multi_unit
        locations=([(None,ui['property_level'])] if include_property else [])+[(u.pk,(prop.unit_number or u.unit_number or ui['single_unit']) if single else u.unit_number) for u in units]
        def breakdown(rows):
            buckets={key:{'label':label,'values':[ZERO]*len(months),'transactions':[]} for key,label in locations}
            values=[ZERO]*len(months)
            for row in rows:
                journal=row['line'].journal
                index=(journal.date.year-start.year)*12+journal.date.month-start.month
                values[index]+=row['change']
                bucket=buckets.setdefault(journal.unit_id,{'label':str(journal.unit) if journal.unit_id else ui['property_level'],'values':[ZERO]*len(months),'transactions':[]})
                bucket['values'][index]+=row['change'];bucket['transactions'].append(row)
            for key,bucket in buckets.items():
                bucket['total']=sum(bucket['values'],ZERO);bucket['unit_key']='property_level' if key is None else str(key)
            return values,list(buckets.values())
        sections=[];income=[ZERO]*len(months);expenses=[ZERO]*len(months);operating=[ZERO]*len(months)
        all_rows=[];operating_rows=[];unclassified=[]
        for kind,totals in [('income',income),('expense',expenses)]:
            accounts=[];section_rows=[]
            for account in chart:
                if account.account_type!=kind:continue
                rows=groups.get(account.pk,{}).get('rows',[])
                if not rows and (not account.is_active or not cleaned.get('show_empty',True)):continue
                values,unit_rows=breakdown(rows)
                for index,value in enumerate(values):totals[index]+=value
                classification=configured.get(str(account.pk),'unclassified')
                sign=1 if kind=='income' else -1
                signed=[dict(row,change=row['change']*sign) for row in rows]
                all_rows.extend(signed);section_rows.extend(rows)
                if rows and classification not in ('operating','non_operating'):unclassified.append(account.name)
                if classification=='operating':
                    operating_rows.extend(signed)
                    for index,value in enumerate(values):operating[index]+=value*sign
                accounts.append({'account':account,'values':values,'units':unit_rows,'total':sum(values,ZERO),'transactions':rows})
            _,unit_totals=breakdown(section_rows)
            sections.append({'key':kind,'title':ui[kind],'accounts':accounts,'units':unit_totals,'values':totals,'total':sum(totals,ZERO)})
        net,net_units=breakdown(all_rows)
        _,operating_units=breakdown(operating_rows)
        from urllib.parse import urlencode
        from django.urls import reverse
        base=reverse('portal:general_ledger')
        selected_units=(['all'] if cleaned.get('unit_all') is not False else (['property_level'] if cleaned.get('unit_property_level') else [])+(['all_units'] if cleaned.get('unit_all_units') else [])+[str(x) for x in cleaned.get('unit_ids',[])])
        def cells(values,account_ids,unit_key=None):
            output=[]
            for index,amount in enumerate(values+[sum(values,ZERO)]):
                begin=months[index] if index<len(months) else start
                end=min(month_start(begin,1)-timezone.timedelta(days=1),today) if index<len(months) else today
                params={'scope':'property:'+str(prop.pk),'basis':cleaned.get('basis','accrual'),'entity':str(cleaned['entity'].pk) if cleaned.get('entity') else '', 'unit':[unit_key] if unit_key else selected_units,'accounts':[str(x) for x in account_ids],'date_range':'custom','start':begin.isoformat(),'end':end.isoformat()}
                output.append({'amount':amount,'url':base+'?'+urlencode(params,doseq=True)})
            return output
        all_ids=[];operating_ids=[]
        for section in sections:
            ids=[row['account'].pk for row in section['accounts']];all_ids.extend(ids)
            for row in section['accounts']:
                account_id=row['account'].pk
                if configured.get(str(account_id))=='operating':operating_ids.append(account_id)
                row['cells']=cells(row['values'],[account_id])
                for unit_row in row['units']:unit_row['cells']=cells(unit_row['values'],[account_id],unit_row['unit_key'])
            section['cells']=cells(section['values'],ids)
            for unit_row in section['units']:unit_row['cells']=cells(unit_row['values'],ids,unit_row['unit_key'])
        for unit_row in net_units:unit_row['cells']=cells(unit_row['values'],all_ids,unit_row['unit_key'])
        for unit_row in operating_units:unit_row['cells']=cells(unit_row['values'],operating_ids,unit_row['unit_key'])
        result.append({'net_cells':cells(net,all_ids),'operating_cells':cells(operating,operating_ids),'property':prop,'label':LedgerFilter.property_label(prop),'sections':sections,'net':net,'net_units':net_units,
            'operating':operating,'operating_units':operating_units,'operating_total':sum(operating,ZERO),'operating_ready':not unclassified,'unclassified':unclassified,
            'total':sum(net,ZERO),'has_activity':bool(all_rows)})
    return {'properties':result,'months':months,'start':start,'end':today,'count':len(result)}


@staff_member_required(login_url='/admin/login/')
@require_GET
def finance_dashboard(request):
    data=request.GET.copy();data.setdefault('scope','properties');data.setdefault('period','three')
    if 'filters' not in request.GET:data.setdefault('show_empty','1')
    from .book_models import AccountingEntity
    entity=AccountingEntity.objects.filter(pk=data.get('entity')).first() if data.get('entity','').isdigit() else AccountingEntity.objects.filter(is_active=True).first()
    from common.models import FormFieldSetting
    defaults=FormFieldSetting.objects.filter(form_key='accounting_books',field_key='defaults').first()
    data.setdefault('basis',entity.default_basis if entity else (defaults.option_labels.get('basis','cash') if defaults else 'cash'))
    if entity:data.setdefault('entity',str(entity.pk))
    form=FinancialFilter(data)
    report=financial_report(form.cleaned_data,timezone.localdate()) if 'search' in request.GET and form.is_valid() else None
    return render(request,'portal/financials.html',{'form':form,'report':report,'ui':wording(),'financial_ui':labels(),'section':'finance','finance_subsection':'dashboard'})
