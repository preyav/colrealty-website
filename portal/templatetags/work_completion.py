from django import template
from portal.historical_work import wording
register=template.Library()
@register.inclusion_tag('portal/work_completion_actions.html')
def completion_actions(work_order):
    return {'work_order':work_order,'ui':wording()}
