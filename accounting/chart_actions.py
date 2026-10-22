from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods
from common.models import FormFieldSetting
from common.audit.services import record_event,snapshot
from .models import ChartAccount,FinancialAccount

FIELDS=['code','name','account_type','cash_asset','parent','fund_type','description','is_active']


def wording():
    return FormFieldSetting.objects.get(form_key='chart_account_actions',field_key='ui').option_labels


def in_use(account):
    return any(relation.related_model._default_manager.filter(**{relation.field.name:account}).exists()
               for relation in ChartAccount._meta.related_objects)


@transaction.atomic
def change_account(account_id,action,actor,request=None):
    if not actor.is_active or not actor.is_staff:raise PermissionError
    ui=wording()
    account=ChartAccount.objects.select_for_update().get(pk=account_id)
    before=snapshot(account,FIELDS)
    if action=='delete':
        if in_use(account):raise ValidationError(ui['used'])
        record_event(action='CHART_ACCOUNT_DELETED',instance=account,actor=actor,request=request,old_values=before,new_values={},reason=ui['delete_reason'])
        account.delete()
    elif action in ('inactivate','activate'):
        if action=='inactivate':
            if FinancialAccount.objects.filter(ledger_account=account,is_active=True).exists():raise ValidationError(ui['bank_active'])
            if account.subaccounts.filter(is_active=True).exists():raise ValidationError(ui['children_active'])
        state=action=='activate'
        if account.is_active==state:return
        account.is_active=state;account.full_clean();account.save(update_fields=['is_active','updated_at'])
        record_event(action='CHART_ACCOUNT_ACTIVATED' if state else 'CHART_ACCOUNT_INACTIVATED',instance=account,actor=actor,request=request,old_values=before,new_values=snapshot(account,FIELDS),reason=ui['status_reason'])
    else:raise ValueError(action)


@staff_member_required(login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def chart_account_action(request,account_id,action):
    if action not in ('delete','inactivate','activate'):raise Http404
    account=get_object_or_404(ChartAccount,pk=account_id);ui=wording();error=None
    if request.method=='POST':
        try:change_account(account.pk,action,request.user,request)
        except ValidationError as exc:error=' '.join(exc.messages)
        except ProtectedError:error=ui['used']
        else:return redirect('portal:finance_accounts')
    return render(request,'portal/chart_account_action.html',{'account':account,'action':action,
        'action_title':ui[action],'action_help':ui[action+'_help'],'action_ui':ui,'error':error,
        'section':'finance','finance_subsection':'accounts'})
