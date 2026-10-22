from django import forms
from .models import LeaseAgreement
from common.field_settings import configure_form

class LeaseAgreementForm(forms.ModelForm):
    change_reason = forms.CharField(max_length=1000)
    class Meta:
        model = LeaseAgreement
        fields = ['kind','title','status','effective_date','signed_date','expiration_date','rent_action','monthly_rent','contact_action','contact_details','named_landlords','named_tenants','paragraph_references','amendment_text','return_deadline','unsigned_outcome','unsigned_rent','unsigned_effective_date','signature_details','review_notes']
        widgets = {name:forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d') for name in ['effective_date','signed_date','expiration_date','return_deadline','unsigned_effective_date']}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name,field in self.fields.items():
            field.widget.attrs['class']='form-control'
            if isinstance(field.widget, forms.Textarea):field.widget.attrs['rows']=3
        self.field_settings = configure_form(self, 'lease_agreement')
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('rent_action')=='changed' and cleaned.get('monthly_rent') is None:
            self.add_error('monthly_rent',self.field_settings['monthly_rent'].error_messages['agreement_rent_required'])
        if cleaned.get('rent_action')!='changed':cleaned['monthly_rent']=None
        if cleaned.get('expiration_date') and cleaned.get('effective_date') and cleaned['expiration_date']<cleaned['effective_date']:
            self.add_error('expiration_date',self.field_settings['expiration_date'].error_messages['before_effective_date'])
        return cleaned
