from decimal import Decimal
from django import forms
from django.utils import timezone
from common.models import FormFieldSetting
from .models import FinancialAccount
from .rent_services import wording


class ConfiguredForm(forms.Form):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        rows={x.field_key:x for x in FormFieldSetting.objects.filter(form_key='rent_ledger')}
        for name,field in self.fields.items():
            if name in rows:
                field.label=rows[name].label;field.help_text=rows[name].help_text
                field.error_messages.update(rows[name].error_messages)
        if 'supporting_link' in self.fields:
            ui=FormFieldSetting.objects.filter(form_key='lease_financials',field_key='ui').first()
            if ui:
                self.fields['supporting_link'].label=ui.option_labels['proof_link']
                self.fields['supporting_link'].help_text=ui.option_labels['proof_help']


class IncomeItemsWidget(forms.Widget):
    template_name='portal/charge_items_widget.html'
    def get_context(self,name,value,attrs):
        import json
        from .models import ChartAccount
        from common.models import FormFieldSetting
        context=super().get_context(name,value,attrs)
        if isinstance(value,str):
            try:value=json.loads(value)
            except (ValueError,TypeError):value=[]
        context['widget']['items']=value or [{}]
        context['widget']['accounts']=ChartAccount.objects.filter(is_active=True,account_type='income').order_by('code')
        row=FormFieldSetting.objects.filter(form_key='rent_ledger',field_key='income_items').first()
        context['widget']['ui']=row.option_labels if row else {}
        return context
    def render(self,name,value,attrs=None,renderer=None):
        from django.template.loader import render_to_string
        from django.utils.safestring import mark_safe
        return mark_safe(render_to_string(self.template_name,self.get_context(name,value,attrs)))
    def value_from_datadict(self,data,files,name):
        import json
        if not hasattr(data,'getlist'):return data.get(name,[])
        ids=data.getlist(name+'_account');amounts=data.getlist(name+'_amount');descriptions=data.getlist(name+'_description')
        return json.dumps([{'account_id':a,'amount':amounts[i] if i<len(amounts) else '', 'description':descriptions[i] if i<len(descriptions) else ''} for i,a in enumerate(ids) if a or (i<len(amounts) and amounts[i])])


class ChargeForm(ConfiguredForm):
    period_start=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    period_end=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    due_date=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    amount=forms.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal('0.01'))
    income_items=forms.JSONField(required=False,widget=IncomeItemsWidget)
    notes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':3}))
    supporting_link=forms.URLField(required=False)

    def clean(self):
        data=super().clean()
        if data.get('period_start') and data.get('period_end') and data['period_end']<data['period_start']:
            self.add_error('period_end',wording()['invalid_charge'])
        if data.get('amount') is not None:
            from .charge_items import normalize_items
            try:data['income_items']=normalize_items(data.get('income_items'),data['amount'])
            except forms.ValidationError as exc:self.add_error('income_items',exc)
        return data


class ReceiptForm(ConfiguredForm):
    received_date=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    amount=forms.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal('0.01'))
    payment_method=forms.ChoiceField(choices=[])
    reference=forms.CharField(max_length=150,required=False)
    financial_account=forms.ModelChoiceField(queryset=FinancialAccount.objects.none(),required=False)
    notes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':3}))
    supporting_link=forms.URLField(required=False)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        row=FormFieldSetting.objects.get(form_key='rent_ledger',field_key='payment_method')
        workspace=FormFieldSetting.objects.filter(form_key='rent_ledger',field_key='workspace').first()
        choices=list(row.option_labels.items())
        if workspace:choices=[('',workspace.option_labels['select_method'])]+choices
        self.fields['payment_method'].choices=choices
        self.fields['financial_account'].queryset=FinancialAccount.objects.filter(is_active=True).exclude(kind='credit_card')

    def clean_received_date(self):
        value=self.cleaned_data['received_date']
        if value>timezone.localdate():raise forms.ValidationError(wording()['invalid_receipt'])
        return value


class ReasonForm(ConfiguredForm):
    reason=forms.CharField(widget=forms.Textarea(attrs={'rows':3}))
