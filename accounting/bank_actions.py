"""Bank configuration actions. Never delete the linked chart account or history."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError,RestrictedError
from django.http import Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from common.models import FormFieldSetting
from common.audit.services import record_event,snapshot
from .models import FinancialAccount,ChartAccount
from .book_models import EntityBank

FIELDS=['name','kind','institution_name','account_last_four','ledger_account','opening_balance','opening_balance_date','notes','is_active']

def wording():return FormFieldSetting.objects.get(form_key='bank_account_actions',field_key='ui').option_labels

def permitted(actor,action):
    verb='delete' if action=='delete' else 'change'
    return actor.is_authenticated and actor.is_active and actor.is_staff and actor.has_perm('accounting.'+verb+'_financialaccount')

def in_use(account):
    if account.ledger_account.journal_lines.exists():return True
    for relation in FinancialAccount._meta.related_objects:
        if relation.related_model is EntityBank:
            for mapping in EntityBank.objects.filter(bank=account):
                if any(rel.related_model._default_manager.filter(**{rel.field.name:mapping}).exists() for rel in EntityBank._meta.related_objects):return True
        elif relation.related_model._default_manager.filter(**{relation.field.name:account}).exists():return True
    return False

@transaction.atomic
def change_bank_account(account_id,action,actor,request=None):
    if action not in ('delete','inactivate','activate'):raise ValueError(action)
    if not permitted(actor,action):raise PermissionDenied
    account=FinancialAccount.objects.select_for_update().get(pk=account_id)
    ChartAccount.objects.select_for_update().get(pk=account.ledger_account_id)
    ui=wording();before=snapshot(account,FIELDS)
    if action=='delete':
        if in_use(account):raise ValidationError(ui['used'])
        mappings=list(EntityBank.objects.select_for_update().filter(bank=account))
        if mappings and not actor.has_perm('accounting.delete_entitybank'):raise PermissionDenied
        for mapping in mappings:
            record_event(action='ENTITY_BANK_DELETED',instance=mapping,actor=actor,request=request,old_values=snapshot(mapping,['entity','bank']),new_values={},reason=ui['delete_reason'])
            mapping.delete()
        record_event(action='FINANCIAL_ACCOUNT_DELETED',instance=account,actor=actor,request=request,old_values=before,new_values={},reason=ui['delete_reason'])
        account.delete()
    else:
        state=action=='activate'
        if account.is_active==state:return
        account.is_active=state;account.full_clean();account.save(update_fields=['is_active','updated_at'])
        record_event(action='FINANCIAL_ACCOUNT_ACTIVATED' if state else 'FINANCIAL_ACCOUNT_INACTIVATED',instance=account,actor=actor,request=request,old_values=before,new_values=snapshot(account,FIELDS),reason=ui['status_reason'])

@login_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def bank_account_action(request,account_id,action):
    if action not in ('delete','inactivate','activate'):raise Http404
    if not permitted(request.user,action):raise PermissionDenied
    account=get_object_or_404(FinancialAccount.objects.select_related('ledger_account'),pk=account_id)
    ui=wording();error=None
    if request.method=='POST':
        try:change_bank_account(account.pk,action,request.user,request)
        except ValidationError as exc:error=' '.join(exc.messages)
        except (ProtectedError,RestrictedError):error=ui['used']
        else:return redirect(reverse('portal:finance_accounts')+'?view=banking')
    return render(request,'portal/bank_account_action.html',{'account':account,'action':action,'action_title':ui[action],'action_help':ui[action+'_help'],'bank_actions':ui,'error':error,'can_inactivate':permitted(request.user,'inactivate'),'section':'finance','finance_subsection':'accounts'})
