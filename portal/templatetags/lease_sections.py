from django import template
from leasing.lease_sections import build_sections
from leasing.lease_summary import summary_navigation

register = template.Library()

@register.simple_tag
def lease_sections(form=None, lease=None):
    if lease is not None and not form:
        return summary_navigation()
    return build_sections(form, lease)
