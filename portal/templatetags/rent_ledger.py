from django import template
from accounting.rent_services import wording
register=template.Library()


@register.inclusion_tag('portal/rent_ledger_link.html')
def rent_ledger_link(lease):
    return {'lease':lease,'ui':wording()}


@register.inclusion_tag('portal/rent_ledger_nav.html')
def rent_ledger_nav(subsection):
    return {'ui':wording(),'subsection':subsection}
