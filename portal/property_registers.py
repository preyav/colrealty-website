"""Staff-facing property registers and a read-only rent balance view."""
import hashlib
import json
from decimal import Decimal
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Q
from django.http import Http404,JsonResponse
from django.shortcuts import render,get_object_or_404,redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from common.models import FormFieldSetting
from common.audit.services import record_event,snapshot
from maintenance.models import PropertyInspection,PropertyAsset
from properties.models import Property,PropertyUnit
from leasing.models import Lease


def labels(form,key='ui'):
    row=FormFieldSetting.objects.filter(form_key=form,field_key=key).first()
    return row.option_labels if row else {}


class RegisterForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        ui=labels('property_registers')
        self.fields['status']=forms.ChoiceField(choices=list(labels('property_registers','inspection_status' if self._meta.model is PropertyInspection else 'asset_status').items()))
        if 'inspection_type' in self.fields:
            self.fields['inspection_type']=forms.ChoiceField(choices=list(labels('property_registers','inspection_type').items()))
            self.fields['assigned_to'].queryset=get_user_model().objects.filter(is_staff=True,is_active=True)
            if self.instance.assigned_to_id:self.fields['assigned_to'].queryset=get_user_model().objects.filter(Q(is_staff=True,is_active=True)|Q(pk=self.instance.assigned_to_id))
        prop=self.data.get('property') if self.is_bound else self.initial.get('property',self.instance.property_id)
        self.fields['unit'].queryset=PropertyUnit.objects.filter(property_id=prop).order_by('unit_number') if str(prop or '').isdigit() else PropertyUnit.objects.none()
        helps={'property':'property_help','unit':'unit_help','title':'title_help','status':'status_help','notes':'notes_help','document_link':'document_help','scheduled_on':'scheduled_help','completed_on':'completed_help','assigned_to':'assigned_help','inspection_type':'type_help','quantity':'quantity_help','manufacturer':'manufacturer_help','model_number':'model_help','serial_number':'serial_help','installed_on':'installed_help','warranty_until':'warranty_help'}
        for name,field in self.fields.items():
            field.label=ui.get(name,field.label);field.help_text=ui.get(helps[name],'')
            if isinstance(field,forms.DateField):field.widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'})
            if isinstance(field.widget,forms.Textarea):field.widget.attrs['rows']=3
        self.fields['document_link'].validators.append(URLValidator(schemes=['https','http']))


class InspectionForm(RegisterForm):
    class Meta:
        model=PropertyInspection
        fields=['property','unit','title','inspection_type','assigned_to','scheduled_on','completed_on','status','document_link','notes']


class AssetForm(RegisterForm):
    class Meta:
        model=PropertyAsset
        fields=['property','unit','title','quantity','status','manufacturer','model_number','serial_number','installed_on','warranty_until','document_link','notes']


REGISTERS={'inspections':(PropertyInspection,InspectionForm),'assets':(PropertyAsset,AssetForm)}


def version(obj):
    return hashlib.sha256(json.dumps(snapshot(obj,[f.name for f in obj._meta.fields]),sort_keys=True,default=str).encode()).hexdigest()


@staff_member_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def property_register(request,kind,record_id=None):
    if kind not in REGISTERS:raise Http404
    model,Form=REGISTERS[kind]
    editing=record_id is not None or request.GET.get('add')=='1'
    verb=('change' if request.method=='POST' else 'view') if record_id else 'add' if editing else 'view'
    if not request.user.has_perm(f'maintenance.{verb}_{model._meta.model_name}'):raise PermissionDenied
    if request.method=='POST' and not editing:raise Http404
    if request.GET.get('units_for') is not None:
        prop=request.GET['units_for']
        rows=PropertyUnit.objects.filter(property_id=prop).order_by('unit_number') if prop.isdigit() else PropertyUnit.objects.none()
        return JsonResponse({'units':[{'id':r.pk,'label':str(r)} for r in rows]})
    ui=labels('property_registers');nav=labels('portal_navigation')
    obj=get_object_or_404(model,pk=record_id) if record_id else model()
    form=None;token='';target=reverse('portal:property_register',args=[kind])
    if editing:
        with transaction.atomic():
            if record_id and request.method=='POST':obj=get_object_or_404(model.objects.select_for_update(),pk=record_id)
            before=snapshot(obj,Form._meta.fields) if obj.pk else {}
            current=version(obj) if obj.pk else 'new'
            form=Form(request.POST if request.method=='POST' else None,instance=obj)
            if request.method=='POST':
                valid=form.is_valid()
                try:matched=signing.loads(request.POST.get('version',''),salt='property-register',max_age=86400)=={'kind':kind,'pk':record_id,'version':current}
                except signing.BadSignature:matched=False
                if not matched:form.add_error(None,ui['stale'])
                if valid and matched:
                    obj=form.save(commit=False)
                    if not obj.pk:obj.created_by=request.user
                    obj.save()
                    record_event(action='PROPERTY_REGISTER_SAVED',instance=obj,actor=request.user,request=request,property_id=obj.property_id,old_values=before,new_values=snapshot(obj,Form._meta.fields))
                    return redirect(target)
            token=signing.dumps({'kind':kind,'pk':record_id,'version':current},salt='property-register')
            if record_id and not request.user.has_perm(f'maintenance.change_{model._meta.model_name}'):
                for field in form.fields.values():field.disabled=True
    rows=model.objects.select_related('property','unit').order_by('-updated_at','pk')
    q=request.GET.get('q','').strip()
    if q:rows=rows.filter(Q(title__icontains=q)|Q(property__street_address__icontains=q)|Q(notes__icontains=q))
    prop=request.GET.get('property','')
    if prop.isdigit():rows=rows.filter(property_id=prop)
    status=request.GET.get('status','')
    if status:rows=rows.filter(status=status)
    statuses=labels('property_registers','inspection_status' if kind=='inspections' else 'asset_status')
    page=Paginator(rows,50).get_page(request.GET.get('page'))
    for row in page:row.status_label=statuses.get(row.status,row.status)
    return render(request,'portal/property_register.html',{'section':'maintenance','maintenance_subsection':kind,'kind':kind,'title':nav.get(kind,''),'ui':ui,'help':ui.get(kind+'_help',''),'form':form,'version':token,'rows':page,'q':q,'property_id':prop,'properties':Property.objects.order_by('street_address'),'status':status,'statuses':statuses,'list_url':target,'can_add':request.user.has_perm(f'maintenance.add_{model._meta.model_name}'),'can_edit':request.user.has_perm(f'maintenance.change_{model._meta.model_name}')})


@staff_member_required(login_url='/accounts/login/')
@require_http_methods(['GET'])
def outstanding_balances(request):
    from common.management.commands.reconcile_lease_rent import reconcile
    today=timezone.localdate();rows=[];zero=Decimal('0.00')
    leases=Lease.objects.filter(Q(rent_charges__isnull=False)|Q(rent_receipts__isnull=False)|Q(fundsevent__isnull=False)).distinct().select_related('unit__property')
    prop=request.GET.get('property','')
    if prop.isdigit():leases=leases.filter(unit__property_id=prop)
    for lease in leases:
        s=reconcile(lease,today)['summary']
        row={'lease':lease,'due':s['charge_balance_through_date'],'overdue':s['overdue_unpaid'],'credit':s['unallocated_credit_through_date'],'net':max(zero,s['net_due_through_date']),'future':s['future_due_unpaid']}
        if any(row[k]!=zero for k in ('due','credit','future')):rows.append(row)
    rows.sort(key=lambda r:(-r['net'],r['lease'].pk))
    return render(request,'portal/outstanding_balances.html',{'section':'rental_balances','ui':labels('outstanding_balances'),'rows':rows,'today':today,'property_id':prop,'properties':Property.objects.order_by('street_address')})
