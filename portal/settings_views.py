import hashlib
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db import transaction,IntegrityError
from django.db.models import Q
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from common.audit.services import record_event
from .settings_access import MODELS,allowed,visible_tabs
from .settings_forms import CompanyForm,BankOwnershipForm,PropertyAccountingForm,FieldLabelsForm,StaffAccessForm,RoleForm,wording

from .settings_forms import ReimbursementPayerForm

FORMS={'payers':ReimbursementPayerForm,'companies':CompanyForm,'banks':BankOwnershipForm,'properties':PropertyAccountingForm,'fields':FieldLabelsForm,'users':StaffAccessForm,'roles':RoleForm}

def state(obj):
    if not obj.pk:return {}
    result=model_to_dict(obj)
    # Never put password hashes or reset inputs in client tokens/audit payloads.
    for key in ('password','last_login'):result.pop(key,None)
    return json.loads(json.dumps(result,default=lambda value:str(value.pk) if hasattr(value,'pk') else str(value)))

def digest(obj):
    values=state(obj)
    if hasattr(obj,'password'):values['password_version']=obj.password
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def row_label(tab,obj):
    if tab=='fields':return obj.form_key.replace('_',' ').title()+' · '+obj.label
    if tab=='users':return (obj.get_full_name() or str(obj))+' · '+(getattr(obj,'email','') or '')
    if tab=='roles':return obj.name
    return str(obj)

@login_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def portal_settings(request):
    tabs=visible_tabs(request.user)
    if not tabs:raise PermissionDenied
    ui=wording();tab=request.GET.get('tab',tabs[0])
    if tab not in MODELS or not allowed(request.user,tab):raise PermissionDenied
    model=MODELS[tab];raw_id=request.POST.get('record_id','') if request.method=='POST' else request.GET.get('edit','')
    if raw_id and not raw_id.isdigit():raise PermissionDenied
    instance=get_object_or_404(model,pk=raw_id) if raw_id else model()
    action='change' if instance.pk else 'add'
    can_edit=allowed(request.user,tab,action) and not (tab=='fields' and not instance.pk)
    if request.method=='POST' and (not can_edit or (tab=='banks' and instance.pk)):raise PermissionDenied
    Form=FORMS[tab];kwargs={'actor':request.user} if tab=='users' else {}
    form=Form(request.POST if request.method=='POST' else None,instance=instance,**kwargs)
    if tab=='banks' and instance.pk:can_edit=False
    if not can_edit:
        for field in form.fields.values():field.disabled=True
    stamp=signing.dumps({'tab':tab,'id':instance.pk,'digest':digest(instance)},salt='portal-settings') if request.method=='GET' else request.POST.get('version','')
    if request.method=='POST':
        try:
            expected=signing.loads(stamp,salt='portal-settings',max_age=3600)
            if expected.get('tab')!=tab or expected.get('id')!=instance.pk:raise signing.BadSignature
            with transaction.atomic():
                if tab in ('users','roles'):
                    from django.contrib.auth import get_user_model
                    list(get_user_model().objects.select_for_update().filter(is_superuser=True,is_active=True).order_by('pk'))
                from django.contrib.auth import get_user_model
                if not allowed(get_user_model().objects.get(pk=request.user.pk),tab,action):raise PermissionDenied
                if instance.pk:
                    locked=model.objects.select_for_update().get(pk=instance.pk)
                    if expected.get('digest')!=digest(locked):raise ValidationError(ui['stale'])
                if form.is_valid():
                    before=state(instance) if instance.pk else {}
                    # ModelForm mutates its instance during validation; use the locked pre-save row for audit.
                    if instance.pk:before=state(locked)
                    saved=form.save()
                    after=state(saved)
                    if tab=='users' and form.cleaned_data.get('password1'):after['password_changed']=True
                    property_id=saved.property_id if tab=='properties' else None
                    record_event(action='PORTAL_CONFIGURATION_SAVED',instance=saved,actor=request.user,request=request,old_values=before,new_values=after,property_id=property_id)
                    if tab=='users' and saved.pk==request.user.pk:update_session_auth_hash(request,saved)
                    messages.success(request,ui['saved'])
                    return redirect(reverse('portal:portal_settings')+f'?tab={tab}&edit={saved.pk}')
        except signing.BadSignature:form.add_error(None,ui['stale'])
        except ValidationError as exc:form.add_error(None,exc)
        except IntegrityError:form.add_error(None,ui['duplicate'])
    records=model.objects.all().order_by('pk');query=request.GET.get('q','').strip()
    if query:
        if tab=='fields':records=records.filter(Q(label__icontains=query)|Q(form_key__icontains=query)|Q(field_key__icontains=query))
        elif tab in ('companies','roles','payers'):records=records.filter(name__icontains=query)
        elif tab=='banks':records=records.filter(Q(bank__name__icontains=query)|Q(entity__name__icontains=query))
        elif tab=='properties':records=records.filter(Q(property__street_address__icontains=query)|Q(entity__name__icontains=query))
        else:
            fields={field.name for field in model._meta.get_fields()};condition=Q()
            for name in ('username','email','first_name','last_name'):
                if name in fields:condition|=Q(**{name+'__icontains':query})
            records=records.filter(condition)
    page=Paginator(records,30).get_page(request.GET.get('page'))
    rows=[{'pk':obj.pk,'label':row_label(tab,obj)} for obj in page]
    return render(request,'portal/settings.html',{'ui':ui,'tabs':[{'key':key,'label':ui[key]} for key in tabs],'tab':tab,'form':form,'record_id':instance.pk,'version':stamp,'rows':rows,'page':page,'q':query,'can_edit':can_edit,'can_add':allowed(request.user,tab,'add') and tab!='fields','section':'settings'})
