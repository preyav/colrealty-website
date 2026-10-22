"""Explicit income itemization without changing a charge or receipt total."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .models import ChartAccount


def normalize_items(items, total):
    if not items:return []
    if not isinstance(items,list) or len(items)>50:raise ValidationError('Supply at most 50 income items.')
    normalized=[]
    for item in items:
        if not isinstance(item,dict):raise ValidationError('Invalid income item.')
        try:
            account=ChartAccount.objects.get(pk=item['account_id'],is_active=True,account_type='income')
            amount=Decimal(str(item['amount']))
            description=str(item.get('description','')).strip()
            if not amount.is_finite() or amount<=0 or amount!=amount.quantize(Decimal('.01')) or len(description)>200:raise ValueError
        except (KeyError,TypeError,ValueError,InvalidOperation,ChartAccount.DoesNotExist):raise ValidationError('Each item needs an active income account, positive amount and description of at most 200 characters.')
        normalized.append({'account_id':account.pk,'amount':format(amount,'.2f'),'description':description})
    if sum((Decimal(x['amount']) for x in normalized),Decimal('0'))!=total:raise ValidationError('Income items must equal the charge amount.')
    if len({a.fund_type for a in ChartAccount.objects.filter(pk__in=[x['account_id'] for x in normalized]) if a.fund_type})>1:raise ValidationError('Income items have conflicting fund types.')
    return normalized


def income_lines(charge, config, amount=None, prior=Decimal('0')):
    items=charge.income_items
    amount=charge.amount if amount is None else amount
    if not items:return [(config.rent_income,amount)]
    accounts={a.pk:a for a in ChartAccount.objects.filter(pk__in=[x['account_id'] for x in items])}
    # Items are paid in displayed order; cumulative slices preserve receipt dates.
    def portion(value):
        remaining=value;result=[]
        for item in items:
            part=min(max(remaining,Decimal('0')),Decimal(item['amount']))
            result.append(part);remaining-=part
        return result
    before=portion(prior);after=portion(prior+amount)
    return [(accounts[item['account_id']],after[i]-before[i]) for i,item in enumerate(items) if after[i]!=before[i]]
