from django import template
from common.models import FormFieldSetting
from leasing.models import LeaseDocument
from common.document_settings import document_type_setting, document_type_choices
register = template.Library()

@register.inclusion_tag('portal/lease_document_panel.html', takes_context=True)
def lease_document_panel(context, lease, agreement=None):
    setting = document_type_setting()
    categories = document_type_choices(setting, LeaseDocument.CATEGORY_CHOICES)
    documents = list(lease.documents.filter(agreement=agreement))
    for document in documents:
        document.configured_category_label = dict(categories).get(document.category, document.category)
    return {'document_ui':{row.field_key:row for row in FormFieldSetting.objects.filter(form_key='lease_document_ui')}, 'document_type_label':setting.label, 'document_type_help':setting.help_text, 'lease':lease, 'agreement':agreement, 'panel_documents':documents, 'document_category':agreement.kind if agreement and agreement.kind in ('extension','amendment','animal') else ('other' if agreement else 'lease'), 'lease_document_categories':categories,
            'csrf_token':context.get('csrf_token')}
