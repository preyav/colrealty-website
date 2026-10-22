from django import template
from accounting.allocation_editor import labels
register=template.Library()
@register.simple_tag
def allocation_action_label():
    return labels()['action']
