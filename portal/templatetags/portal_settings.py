from django import template
from portal.settings_access import visible_tabs
from portal.settings_forms import wording
register=template.Library()

@register.inclusion_tag('portal/settings_navigation.html',takes_context=True)
def settings_navigation(context):
    request=context.get('request')
    return {'visible':bool(request and visible_tabs(request.user)),'ui':wording(),'active':context.get('section')=='settings'}
