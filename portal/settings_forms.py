"""Portal editors over existing configuration; no parallel settings store."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.contrib.auth.password_validation import validate_password
from copy import copy
import hashlib
from django.apps import apps
from django.db.models import Q
from common.models import FormFieldSetting
from accounting.book_models import AccountingEntity,EntityBank,PropertyBooks,BookPosting
from accounting.models import ChartAccount,FinancialAccount


def wording():
    row=FormFieldSetting.objects.filter(form_key='portal_settings',field_key='ui').first()
    return row.option_labels if row else {}

class SettingsForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        rows={r.field_key:r for r in FormFieldSetting.objects.filter(form_key='portal_settings')}
        for name,field in self.fields.items():
            if name in rows:
                field.label=rows[name].label;field.help_text=rows[name].help_text
                if isinstance(field,forms.ChoiceField) and not isinstance(field,forms.ModelChoiceField) and rows[name].option_labels:
                    field.choices=[(key,rows[name].option_labels.get(str(key),label)) for key,label in field.choices]
        for field in self.fields.values():
            if isinstance(field.widget,forms.Textarea):field.widget.attrs['rows']=3

class CompanyForm(SettingsForm):
    class Meta:
        model=AccountingEntity
        fields=['name','default_basis','is_active']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not self.instance.pk:
            row=FormFieldSetting.objects.filter(form_key='accounting_books',field_key='defaults').first()
            if row and row.option_labels.get('basis') in dict(self.fields['default_basis'].choices):self.initial['default_basis']=row.option_labels['basis']

class BankOwnershipForm(SettingsForm):
    class Meta:
        model=EntityBank
        fields=['entity','bank']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk:
            for field in self.fields.values():field.disabled=True
        else:
            self.fields['entity'].queryset=AccountingEntity.objects.filter(is_active=True)
            self.fields['bank'].queryset=FinancialAccount.objects.filter(is_active=True,entity_book__isnull=True,ledger_account__account_type='asset').exclude(kind='credit_card')

class PropertyAccountingForm(SettingsForm):
    class Meta:
        model=PropertyBooks
        fields=['property','entity','operating_bank','deposit_bank','reserve','rent_income','receivable','payable','deposits','advances','credits','owner_equity','enabled']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk:self.fields['property'].disabled=True
        else:self.fields['property'].queryset=self.fields['property'].queryset.filter(books__isnull=True)
        entity_id=self.data.get(self.add_prefix('entity'),self.instance.entity_id) if self.is_bound else self.instance.entity_id
        entity_id=int(entity_id) if str(entity_id).isdigit() else None
        for name in ['operating_bank','deposit_bank']:
            self.fields[name].queryset=FinancialAccount.objects.filter(entity_book__entity_id=entity_id).exclude(kind='credit_card').filter(Q(is_active=True)|Q(pk=getattr(self.instance,name+'_id',None)))
        for name,kind in {'rent_income':'income','receivable':'asset','payable':'liability','deposits':'liability','advances':'liability','credits':'liability','owner_equity':'equity'}.items():
            self.fields[name].queryset=ChartAccount.objects.filter(Q(is_active=True,account_type=kind)|Q(pk=getattr(self.instance,name+'_id',None))).order_by('code','name')
        if self.instance.pk and BookPosting.objects.filter(journal__property_id=self.instance.property_id).exists():
            for name in self.fields:
                if name not in ('reserve','enabled','operating_bank','deposit_bank'):self.fields[name].disabled=True

class FieldLabelsForm(SettingsForm):
    class Meta:
        model=FormFieldSetting
        fields=['label','help_text']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.error_fields={}
        for index,(key,value) in enumerate((self.instance.error_messages or {}).items()):
            name='error_'+hashlib.sha256(key.encode()).hexdigest();self.error_fields[name]=key
            self.fields[name]=forms.CharField(label=key.replace('_',' ').capitalize(),initial=value,required=False)
        self.option_fields={}
        for index,(key,value) in enumerate((self.instance.option_labels or {}).items()):
            name='option_'+hashlib.sha256(key.encode()).hexdigest();self.option_fields[name]=key
            if self.instance.form_key=='financial_account_classification' and key=='classification':
                self.fields[name]=forms.ChoiceField(label=wording()['classification'],choices=[(k,wording()[k]) for k in ('unclassified','operating','non_operating')],initial=value)
            elif key=='basis' and self.instance.form_key=='accounting_books' and self.instance.field_key=='defaults':
                self.fields[name]=forms.ChoiceField(label=wording()['default_basis'],choices=AccountingEntity._meta.get_field('default_basis').choices,initial=value)
            else:
                self.fields[name]=forms.CharField(label=key.replace('_',' ').capitalize(),initial=value,required=False,widget=forms.Textarea(attrs={'rows':2}) if len(str(value))>90 else forms.TextInput)
    def save(self,commit=True):
        obj=super().save(commit=False);options=dict(obj.option_labels or {})
        for name,key in self.option_fields.items():options[key]=self.cleaned_data[name]
        obj.option_labels=options
        errors=dict(obj.error_messages or {})
        for name,key in self.error_fields.items():errors[key]=self.cleaned_data[name]
        obj.error_messages=errors
        if commit:obj.save()
        return obj

User=get_user_model()
USER_FIELDS=list(dict.fromkeys([User.USERNAME_FIELD]+[name for name in ['email','first_name','last_name','is_active','is_staff','groups'] if name in {f.name for f in User._meta.get_fields()}]))
class StaffAccessForm(SettingsForm):
    password1=forms.CharField(required=False,strip=False,widget=forms.PasswordInput(render_value=False))
    password2=forms.CharField(required=False,strip=False,widget=forms.PasswordInput(render_value=False))
    class Meta:
        model=User
        fields=USER_FIELDS
    def __init__(self,*args,actor=None,**kwargs):
        self.actor=actor
        super().__init__(*args,**kwargs)
        if self.instance.pk and apps.is_installed('allauth.account') and 'email' in self.fields:
            self.fields['email'].disabled=True
            self.fields['email'].help_text=wording()['verified_email_help']
        if not self.instance.pk:
            self.initial.setdefault('is_staff',True)
            self.fields['password1'].required=True;self.fields['password2'].required=True
    def clean_email(self):
        from django.core.validators import validate_email
        value=self.cleaned_data.get('email','')
        if value:validate_email(value)
        if value and not self.instance.pk and apps.is_installed('allauth.account'):
            from allauth.account.models import EmailAddress
            if EmailAddress.objects.filter(email__iexact=value).exists():raise forms.ValidationError(wording()['email_in_use'])
        return value
    def clean(self):
        data=super().clean();first=data.get('password1');second=data.get('password2')
        if first or second:
            if first!=second:self.add_error('password2',wording()['password_mismatch'])
            else:
                candidate=copy(self.instance)
                for key in USER_FIELDS:
                    if key in data and key!='groups':setattr(candidate,key,data[key])
                validate_password(first,candidate)
        if self.actor and self.instance.pk==self.actor.pk:
            if not data.get('is_active') or not data.get('is_staff'):raise forms.ValidationError(wording()['self_access'])
        # Superuser status is never granted or removed by this form.
        if self.instance.pk and self.instance.is_superuser and (not data.get('is_active') or not data.get('is_staff')):
            if not User.objects.filter(is_superuser=True,is_active=True,is_staff=True).exclude(pk=self.instance.pk).exists():raise forms.ValidationError(wording()['last_admin'])
        return data
    def save(self,commit=True):
        obj=super().save(commit=False)
        if self.cleaned_data.get('password1'):obj.set_password(self.cleaned_data['password1'])
        adding=obj.pk is None
        if commit:
            obj.save();self.save_m2m()
            if adding and obj.email and apps.is_installed('allauth.account'):
                from allauth.account.models import EmailAddress
                EmailAddress.objects.get_or_create(user=obj,email=obj.email,defaults={'primary':True,'verified':False})
        return obj

class RoleForm(SettingsForm):
    class Meta:
        model=Group
        fields=['name','permissions']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['permissions'].queryset=Permission.objects.select_related('content_type').order_by('content_type__app_label','codename')

from accounting.reimbursement_models import ReimbursementPayer

class ReimbursementPayerForm(SettingsForm):
    class Meta:
        model=ReimbursementPayer
        fields=['name','entity','liability_account','prepaid_account','is_active']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['entity'].queryset=AccountingEntity.objects.filter(is_active=True)
        for field,kind in [('liability_account','liability'),('prepaid_account','asset')]:
            self.fields[field].queryset=ChartAccount.objects.filter(is_active=True,account_type=kind,financial_account__isnull=True)
