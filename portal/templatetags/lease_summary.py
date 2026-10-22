from django import template
from leasing.lease_summary import management_summary
register = template.Library()


@register.simple_tag
def lease_management_summary(lease):
    return management_summary(lease)


@register.simple_tag
def lease_workspace(lease):
    from common.models import FormFieldSetting
    from accounting.rent_services import ledger_data
    setting=FormFieldSetting.objects.get(form_key='lease_workspace',field_key='ui')
    from accounting.lease_financials import financial_timeline,ledger_display_metadata
    ledger=ledger_data(lease)
    financial_ui=FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui').option_labels
    return {'ui':setting.option_labels,'ledger':ledger,'financial_ui':financial_ui,'timeline':ledger_display_metadata(lease,financial_timeline(ledger))}
