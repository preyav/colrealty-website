from django import forms
from django.db.models import Q

from .models import ChartAccount, FinancialAccount


class ChartAccountForm(forms.ModelForm):
    account_level=forms.ChoiceField(choices=[],widget=forms.RadioSelect)
    fund_type=forms.ChoiceField(choices=[],required=False)

    class Meta:
        model = ChartAccount
        fields = ["name", "account_type", "cash_asset", "account_level", "parent", "code", "fund_type", "description", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "Example: 1010"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from common.models import FormFieldSetting
        from .workspace import configure_form
        rows={row.field_key:row for row in FormFieldSetting.objects.filter(form_key='chart_account_details')}
        self.fields['account_level'].choices=list(rows['account_level'].option_labels.items())
        self.fields['account_level'].label=rows['account_level'].label
        self.fields['account_level'].help_text=rows['account_level'].help_text
        self.fields['fund_type'].choices=[('','---------')]+list(FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='chart_fund_type').option_labels.items())
        if self.instance.pk and self.instance.fund_type not in dict(self.fields['fund_type'].choices):
            self.fields['fund_type'].choices.append((self.instance.fund_type,self.instance.fund_type))
        self.initial['account_level']='subaccount' if self.instance.parent_id else 'parent'
        if not self.instance.pk:self.initial['fund_type']=rows['defaults'].option_labels.get('fund_type','')
        descendants=set()
        if self.instance.pk:
            descendants.add(self.instance.pk)
            relationships=list(ChartAccount.objects.values_list('pk','parent_id'))
            changed=True
            while changed:
                before=len(descendants)
                descendants.update(pk for pk,parent in relationships if parent in descendants)
                changed=len(descendants)!=before
        self.fields['parent'].queryset=ChartAccount.objects.filter(Q(is_active=True)|Q(pk=self.instance.parent_id)).exclude(pk__in=descendants).order_by('code','name')
        self.fields['cash_asset'].disabled=True
        self.initial['cash_asset']=self.instance.cash_asset if self.instance.pk else False
        self.cash_asset_visible=bool(self.instance.pk and self.instance.account_type=='asset')
        linked=FinancialAccount.objects.filter(ledger_account_id=self.instance.pk).first() if self.instance.pk else None
        if linked:
            self.fields['account_type'].disabled=True
            if linked.kind in ('bank','trust','cash'):
                self.fields['cash_asset'].disabled=True
                self.initial['cash_asset']=True
            self.fields['account_type'].help_text=rows['linked_help'].help_text
        configure_form(self,'chart')
        if self.instance.pk and self.instance.journal_lines.exists():
            from .general_ledger import wording
            self.fields['account_type'].disabled=True
            self.fields['account_type'].help_text=wording()['posted_account_type']
        if linked:self.fields['account_type'].help_text=rows['linked_help'].help_text

    def clean(self):
        data=super().clean()
        from common.models import FormFieldSetting
        errors=FormFieldSetting.objects.get(form_key='chart_account_details',field_key='errors').option_labels
        if data.get('account_level')=='parent':data['parent']=None
        elif data.get('account_level')=='subaccount' and not data.get('parent'):
            self.add_error('parent',errors['parent_required'])
        return data

    def clean_is_active(self):
        is_active = self.cleaned_data.get("is_active")
        if self.instance.pk and not is_active:
            financial_account = getattr(self.instance, "financial_account", None)
            if financial_account and financial_account.is_active:
                raise forms.ValidationError(
                    "Deactivate the linked financial account before deactivating this chart account."
                )
        return is_active


class FinancialAccountForm(forms.ModelForm):
    class Meta:
        model = FinancialAccount
        fields = [
            "name", "kind", "ledger_account", "institution_name",
            "account_last_four", "opening_balance", "opening_balance_date",
            "notes", "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "kind": forms.Select(attrs={"class": "form-control"}),
            "ledger_account": forms.Select(attrs={"class": "form-control"}),
            "institution_name": forms.TextInput(attrs={"class": "form-control"}),
            "account_last_four": forms.TextInput(attrs={"class": "form-control", "maxlength": 4}),
            "opening_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "opening_balance_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ChartAccount.objects.filter(is_active=True).order_by("code")
        if self.instance.pk and self.instance.ledger_account_id:
            queryset = ChartAccount.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.ledger_account_id)
            ).order_by("code")
        self.fields["ledger_account"].queryset = queryset

    def clean(self):
        cleaned = super().clean()
        opening_balance = cleaned.get("opening_balance")
        opening_balance_date = cleaned.get("opening_balance_date")
        if opening_balance and not opening_balance_date:
            self.add_error(
                "opening_balance_date",
                "Enter the effective date for this opening balance.",
            )
        return cleaned
