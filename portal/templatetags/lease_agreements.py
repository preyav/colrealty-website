from django import template
from leasing.agreement_history import agreement_history
from common.models import FormFieldSetting
from django.urls import reverse
register=template.Library()

@register.inclusion_tag('portal/lease_agreement_history.html',takes_context=True)
def lease_agreement_history(context,lease,compact=False):
    data=agreement_history(lease)
    data['agreement_ui']={row.field_key:row for row in FormFieldSetting.objects.filter(form_key='lease_agreement_page')}
    documents = list(lease.documents.all())
    def reference_links(agreement_id, category):
        links = []
        for document in documents:
            if document.agreement_id != agreement_id or document.category != category:
                continue
            url = document.url
            if document.storage_key:
                url = reverse('portal:lease_document_download', args=[lease.pk, document.pk]) + '?view=1'
            if url:
                links.append({'url': url, 'title': document.title})
        return links
    data['original_reference_links'] = reference_links(None, 'lease')
    for item in data['history_items']:
        agreement = item['agreement']
        category = agreement.kind if agreement.kind in ('extension', 'amendment', 'animal') else 'other'
        item['reference_links'] = reference_links(agreement.pk, category)
    data['amendment_setting'] = FormFieldSetting.objects.get(form_key='lease_agreement', field_key='amendment_text')
    # Reverse only the display list; agreement_history computes terms oldest first.
    data['history_items'] = sorted(data['history_items'], key=lambda item: (item['agreement'].effective_date, item['agreement'].signed_date or item['agreement'].effective_date, item['agreement'].pk), reverse=True)
    data['summary_ui'] = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key='lease_summary')}
    data['compact']=compact
    data['csrf_token']=context.get('csrf_token')
    return data
