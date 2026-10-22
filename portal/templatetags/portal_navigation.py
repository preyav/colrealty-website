from django import template
from django.urls import reverse
from portal.property_registers import labels
register=template.Library()

@register.simple_tag
def portal_nav_labels():return labels('portal_navigation')

@register.inclusion_tag('portal/group_navigation.html',takes_context=True)
def portal_group(context,group):
    ui=labels('portal_navigation');section=context.get('section');sub=context.get('maintenance_subsection')
    if group=='rentals':
        entries=[('properties','properties'),('leases','leases'),('tenants','tenants'),('owners','owners'),('outstanding','outstanding_balances')]
        active={'properties':'properties','leases':'leases','tenants':'tenants','owners':'owners','rental_balances':'outstanding'}.get(section)
        icon='🏠'
    else:
        entries=[('vendors','vendors'),('work_orders','work_orders'),('inspections',None),('assets',None),('requests','maintenance')]
        active='vendors' if section=='vendors' else (sub or 'requests') if section=='maintenance' else None
        icon='🛠'
    items=[{'key':key,'label':ui.get(key,''),'url':reverse('portal:'+route) if route else reverse('portal:property_register',args=[key])} for key,route in entries]
    return {'group':group,'title':ui.get(group,''),'items':items,'active':active,'icon':icon}

@register.simple_tag
def property_financial_labels():return labels('property_financials')
