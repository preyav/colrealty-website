from django import template
from accounting.workspace import workspace_ui,navigation,configure_form
register=template.Library()

@register.simple_tag
def accounting_ui():
    return workspace_ui()

@register.simple_tag
def accounting_form(form,kind):
    if kind!='chart':configure_form(form,kind)
    return ''

@register.inclusion_tag('portal/accounting_navigation.html',takes_context=True)
def accounting_navigation(context):
    request=context.get('request')
    subsection=context.get('finance_subsection')
    banking=request and request.GET.get('view')=='banking'
    active={'general_ledger':'general_ledger','rent':'rent','dashboard':'financials','vendor_invoices':'bills','quickbooks':'quickbooks','accounts':'banking' if banking else 'chart'}.get(subsection)
    if request and getattr(request,'resolver_match',None) and request.resolver_match.url_name in ('finance_financial_account_add','finance_financial_account_edit'):active='banking'
    return {'items':navigation(),'ui':workspace_ui(),'active':active}
