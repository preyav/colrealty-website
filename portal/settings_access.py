"""Configuration access follows existing Django permissions, not a new role store."""
from accounting.book_models import AccountingEntity,EntityBank,PropertyBooks
from common.models import FormFieldSetting
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounting.reimbursement_models import ReimbursementPayer

MODELS={'companies':AccountingEntity,'banks':EntityBank,'properties':PropertyBooks,'fields':FormFieldSetting,'users':get_user_model(),'roles':Group,'payers':ReimbursementPayer}

def allowed(user,tab,action='view'):
    if not user.is_authenticated or not user.is_active or not user.is_staff:return False
    if tab in ('users','roles'):return user.is_superuser
    if user.is_superuser:return True
    model=MODELS.get(tab)
    if model is None:return False
    opts=model._meta
    if action=='view':
        return any(user.has_perm(f'{opts.app_label}.{verb}_{opts.model_name}') for verb in ('view','add','change'))
    return user.has_perm(f'{opts.app_label}.{action}_{opts.model_name}')

def visible_tabs(user):return [key for key in MODELS if allowed(user,key)]
