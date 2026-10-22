from django import template
from common.models import FormFieldSetting

register = template.Library()


@register.simple_tag
def owner_flow_actions():
    try:
        return FormFieldSetting.objects.get(form_key="owner_profile", field_key="flow_actions").option_labels
    except FormFieldSetting.DoesNotExist as exc:
        raise RuntimeError("Run python manage.py seed_owner_flow_actions before using owner forms.") from exc


@register.simple_tag
def ownership_form_fields(form):
    form.order_fields(["owner", "ownership_percentage", "start_date", "end_date", "is_primary_contact", "statement_recipient_name", "statement_recipient_email", "maintenance_approval_limit", "distribution_instructions", "notes"])
    return form
