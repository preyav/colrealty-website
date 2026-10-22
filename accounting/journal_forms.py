from datetime import timedelta
from django import forms
from django.forms import formset_factory
from django.utils import timezone
from common.models import FormFieldSetting
from properties.models import Property,PropertyUnit
from .models import ChartAccount
from .book_models import AccountingEntity
from .general_ledger import wording,funds


class Configured(forms.Form):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);ui=wording()
        for key,field in self.fields.items():field.label=ui.get(key,field.label)


class UnitSelect(forms.Select):
    def create_option(self,name,value,label,selected,index,subindex=None,attrs=None):
        option=super().create_option(name,value,label,selected,index,subindex,attrs)
        if hasattr(value,'instance'):option['attrs']['data-property']=value.instance.property_id
        return option


class AccountCheckboxes(forms.CheckboxSelectMultiple):
    def create_option(self,name,value,label,selected,index,subindex=None,attrs=None):
        option=super().create_option(name,value,label,selected,index,subindex,attrs)
        if hasattr(value,'instance'):
            account=value.instance
            option['attrs'].update({'data-account-type':account.account_type,'data-type-label':account.get_account_type_display(),'data-account-name':account.name})
        return option


class LedgerFilter(Configured):
    entity=forms.ModelChoiceField(queryset=AccountingEntity.objects.all(),required=False)
    basis=forms.ChoiceField(choices=[('cash','Cash basis'),('accrual','Accrual basis')],required=False)

    scope=forms.ChoiceField(choices=[])
    unit=forms.MultipleChoiceField(choices=[],required=False,widget=forms.CheckboxSelectMultiple)
    accounts=forms.ModelMultipleChoiceField(queryset=ChartAccount.objects.all().order_by('account_type','code'),required=False,widget=AccountCheckboxes)
    date_range=forms.ChoiceField(choices=[],required=False)
    start=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    end=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    fund_type=forms.ChoiceField(choices=[],required=False)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);ui=wording()
        if self.is_bound and self.data.get('scope')=='property':
            self.data=self.data.copy();self.data['scope']='property:'+str(self.data.get('property',''))
        self.fields['scope'].label=ui.get('properties',ui['property'])
        units=list(PropertyUnit.objects.select_related('property').all())
        self.unit_properties={str(unit.pk):unit.property_id for unit in units}
        counts={}
        for unit in units:counts[unit.property_id]=counts.get(unit.property_id,0)+1
        self.unit_labels={str(unit.pk):((unit.property.unit_number or unit.unit_number or ui['single_unit_label']) if counts[unit.property_id]==1 and not unit.property.is_multi_unit else (unit.unit_number or str(unit))) for unit in units}
        self.fields['unit'].choices=[('all',ui['all_properties']),('property_level',ui['property_level']),('all_units',ui['all_units'])]+[(str(unit.pk),str(unit)) for unit in units]
        if self.is_bound and not hasattr(self.data,'getlist'):
            self.data=self.data.copy();value=self.data.get('unit',[])
            if not isinstance(value,(list,tuple)):self.data['unit']=[str(value)] if value else []
        self.fields['date_range'].choices=[('month',ui['month']),('last30',ui['last30']),('year',ui['year']),('custom',ui['custom'])]
        self.fields['scope'].choices=[('properties',ui.get('all_properties',ui['all_scope']))]+[('property:'+str(prop.pk),self.property_label(prop)) for prop in Property.objects.all()]
        self.fields['fund_type'].choices=[('',ui['all_funds']),('__unknown__',ui['unknown'])]+list(funds().items())

    @staticmethod
    def property_label(prop):
        kind=prop.property_type_other if prop.property_type=='other' and prop.property_type_other else prop.get_property_type_display()
        return str(prop)+((' · '+kind) if kind else '')

    def clean(self):
        data=super().clean();ui=wording()
        data['basis']=data.get('basis') or 'accrual'
        from .book_models import AccountingEntity
        if AccountingEntity.objects.exists() and not data.get('entity'):self.add_error('entity','Select one accounting entity.')
        if data.get('entity') and data.get('scope','').startswith('property:'):
            from .book_models import PropertyBooks
            if not PropertyBooks.objects.filter(entity=data['entity'],property_id=data['scope'].split(':')[1]).exists():self.add_error('scope','Property belongs to another accounting entity.')
        if data.get('start') and data.get('end') and data['end']<data['start']:self.add_error('end',ui['date_order'])
        selection=data.get('scope','')
        data['property']=None
        if selection.startswith('property:'):
            data['property']=Property.objects.filter(pk=selection.split(':',1)[1]).first()
            data['scope']='property'
            if not data['property']:self.add_error('scope',ui['property_required'])
        selections=data.get('unit') or ['all']
        if 'all' in selections:selections=['all']
        if 'all_units' in selections and data.get('property'):self.add_error('unit',ui['unit_mismatch'])
        ids=[value for value in selections if value not in ('all','property_level','all_units')]
        if data.get('property') and any(self.unit_properties.get(value)!=data['property'].pk for value in ids):self.add_error('unit',ui['unit_mismatch'])
        data['unit']=None
        data['unit_ids']=ids
        data['unit_property_level']='property_level' in selections
        data['unit_all']='all' in selections
        data['unit_all_units']='all_units' in selections
        return data


class UnitNumberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.unit_number


class JournalForm(Configured):
    entity=forms.ModelChoiceField(queryset=AccountingEntity.objects.filter(is_active=True),required=False)
    basis=forms.ChoiceField(choices=[('both','Cash and accrual'),('cash','Cash basis'),('accrual','Accrual basis')],initial='both',required=False)

    date=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    property=forms.ModelChoiceField(queryset=Property.objects.all(),required=False)
    unit=UnitNumberChoiceField(queryset=PropertyUnit.objects.select_related('property'),required=False,widget=UnitSelect)
    fund_type=forms.ChoiceField(choices=[],required=False)
    memo=forms.CharField(widget=forms.Textarea(attrs={'rows':3}))

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['fund_type'].choices=[('',wording()['unknown'])]+list(funds().items())


class JournalLineForm(Configured):
    account=forms.ModelChoiceField(queryset=ChartAccount.objects.filter(is_active=True).order_by('code','name'))
    debit=forms.DecimalField(max_digits=14,decimal_places=2,min_value=0,required=False)
    credit=forms.DecimalField(max_digits=14,decimal_places=2,min_value=0,required=False)

JournalLines=formset_factory(JournalLineForm,extra=0,min_num=2,validate_min=True,max_num=50,validate_max=True,absolute_max=50)


class ReverseForm(Configured):
    date=forms.DateField(widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}))
    memo=forms.CharField(widget=forms.Textarea(attrs={'rows':3}))
