from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting

from django import forms
from leasing.models import LeaseAgreement

class InitialAgreementForm(forms.ModelForm):
    change_reason = forms.CharField(label='Reason for recording', max_length=1000)
    class Meta:
        model = LeaseAgreement
        fields = ['kind','title','status','effective_date','signed_date','expiration_date','rent_action','monthly_rent','contact_action','contact_details','named_landlords','named_tenants','paragraph_references','amendment_text','return_deadline','unsigned_outcome','unsigned_rent','unsigned_effective_date','signature_details','review_notes']
        widgets = {name:forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d') for name in ['effective_date','signed_date','expiration_date','return_deadline','unsigned_effective_date']}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name,field in self.fields.items():
            field.widget.attrs['class']='form-control'
            if isinstance(field.widget, forms.Textarea):field.widget.attrs['rows']=3
        self.fields['amendment_text'].label='Amendment wording (exactly as written)'
        self.fields['unsigned_rent'].label='Rent if extension is not returned'
        self.fields['unsigned_effective_date'].label='Conditional rent effective date'
        descriptions={'effective_date':'Effective date expressly stated in the document, separate from its signature date.', 'signed_date':'Latest signature date on this document; enter individual dates in Signature Details.', 'rent_action':'Choose Changed only when this document expressly changes signed-agreement rent.', 'monthly_rent':'Signed-agreement rent only. Record any conditional unsigned-extension rent separately.', 'amendment_text':'Copy the amendment or addendum wording exactly, preserving paragraph references.', 'named_tenants':'Transcribe the named parties. This entry does not automatically release existing tenants.', 'return_deadline':'Deadline stated for signing and returning this document.', 'unsigned_rent':'Rent stated only for the condition that the extension is not signed and returned.', 'review_notes':'Record document-specific ambiguity or repeated wording without automatically changing financial balances.', 'change_reason':'This reason is included in the permanent Audit Ledger.'}
        for name,field in self.fields.items():
            field.lease_information=[{'label':field.label,'text':descriptions.get(name,'Enter the value expressly stated for '+field.label.lower()+'. Leave optional entries blank when not specified.')}]


class Command(BaseCommand):
    help = 'Initialize editable agreement field wording without overwriting existing settings.'

    @transaction.atomic
    def handle(self, *args, **options):
        form = InitialAgreementForm()
        for name, field in form.fields.items():
            errors = {key: str(value) for key, value in field.error_messages.items()}
            if name == 'monthly_rent':
                errors['agreement_rent_required'] = 'Enter the rent stated in the agreement.'
            if name == 'expiration_date':
                errors['before_effective_date'] = 'Expiration cannot precede the stated effective date.'
            FormFieldSetting.objects.get_or_create(
                form_key='lease_agreement', field_key=name,
                defaults={'label': 'Agreement Type' if name == 'kind' else str(field.label),
                          'help_text': '\n\n'.join(item['text'] for item in field.lease_information),
                          'option_labels': {str(code): str(label) for code, label in getattr(field, 'choices', [])},
                          'error_messages': errors},
            )
        self.stdout.write(self.style.SUCCESS('Agreement field settings initialized; existing settings preserved.'))
