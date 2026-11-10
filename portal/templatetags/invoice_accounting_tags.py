from django import template
from accounting.book_models import BillAccounting, BookPosting
from common.models import FormFieldSetting
from portal.invoice_accounting import FORM_KEY, FIELD_DEFAULTS, wording

register = template.Library()

@register.inclusion_tag('portal/invoice_accounting_summary.html')
def invoice_accounting_summary(invoice):
    details = BillAccounting.objects.filter(invoice=invoice).select_related('expense_account').first()
    rows = []
    settings = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key=FORM_KEY)}
    if details:
        for key, (label, help_text) in FIELD_DEFAULTS.items():
            rows.append({'label': settings[key].label if key in settings else label, 'value': getattr(details, key), 'is_date': key != 'expense_account'})
    return {'rows': rows, 'ui': wording(), 'posted': BookPosting.objects.filter(source_key='bill:' + str(invoice.pk)).exists()}
