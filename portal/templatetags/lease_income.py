from django import template,forms
from django.utils import timezone
from common.models import FormFieldSetting
from accounting.book_models import PropertyBooks
from accounting.financials import financial_report,labels
from accounting.book_reports import coverage
register=template.Library()

def statement_context(context,property,anchor='property-financials',allow_ledger=False):
    request=context.get('request')
    row=FormFieldSetting.objects.filter(form_key='lease_income_statement',field_key='ui').first()
    if not allow_ledger:
        row=FormFieldSetting.objects.filter(form_key='property_income_statement',field_key='ui').first() or row
    ui=row.option_labels if row else {}
    params=request.GET.copy() if request else {}
    active='ledger' if allow_ledger and params.get('lease_financial_view')=='ledger' else 'income'
    def link(value):
        from urllib.parse import urlencode
        copy=params.copy();copy['lease_financial_view']=value
        return (request.path if request else '')+'?'+(copy.urlencode() if hasattr(copy,'urlencode') else urlencode(copy))+'#'+anchor
    result={'ui':ui,'active':active,'income_url':link('income'),'ledger_url':link('ledger'),'report':None,'form':None,'config':None,'incomplete':False,'preserved':[(key,value) for key in params for value in (params.getlist(key) if hasattr(params,'getlist') else [params[key]]) if key not in ('income_period','income_basis','lease_financial_view')],'action':(request.path if request else '')+'#'+anchor}
    if not row or active=='ledger':return result
    config=PropertyBooks.objects.select_related('entity').filter(property_id=property.pk).first()
    result['config']=config
    financial_ui=dict(labels());financial_ui['classification_help']=ui['classification_help'];financial_ui['expand']=ui.get('expand_rows',financial_ui['expand']);financial_ui['collapse']=ui.get('collapse_rows',financial_ui['collapse']);result['financial_ui']=financial_ui
    form=forms.Form({'income_period':params.get('income_period',ui['default_period']),'income_basis':params.get('income_basis',config.entity.default_basis if config else 'cash')})
    form.fields['income_period']=forms.ChoiceField(label=ui['period'],choices=[(key,financial_ui[key]) for key in ('three','six','twelve','year','month')])
    form.fields['income_basis']=forms.ChoiceField(label=ui['basis'],choices=[('cash',ui['cash']),('accrual',ui['accrual'])],widget=forms.RadioSelect)
    result['form']=form
    if config and form.is_valid():
        result['report']=financial_report({'period':form.cleaned_data['income_period'],'basis':form.cleaned_data['income_basis'],'property':property,'scope':'property','entity':config.entity,'unit_all':True,'show_empty':True if getattr(getattr(request,'user',None),'is_authenticated',False) else ui.get('show_empty_accounts','1')=='1'},timezone.localdate())
        result['incomplete']=not coverage(config)['complete']
        user=getattr(request,'user',None)
        if user and user.is_authenticated and user.is_staff:
            from accounting.statement_preferences import StatementRowsForm,apply_display,wording
            from django.urls import reverse
            # Build the complete financial statement before changing visible rows.
            result.update(apply_display(result['report'],user))
            result['rows_form']=StatementRowsForm(user=user)
            result['rows_ui']=wording()
            result['rows_action']=reverse('portal:property_financials',args=[property.pk])+'#property-financials'
    return result


@register.simple_tag(takes_context=True)
def lease_income_statement(context,lease):
    # Compatibility for existing templates; Property 360 owns the report UI.
    return statement_context(context,lease.unit.property,anchor='lease-financials',allow_ledger=True)
