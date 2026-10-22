"""Non-bank vendor settlements and their separately recorded reimbursements."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ReimbursementPayer(models.Model):
    name = models.CharField(max_length=180)
    entity = models.ForeignKey('accounting.AccountingEntity', on_delete=models.PROTECT)
    liability_account = models.ForeignKey('accounting.ChartAccount', on_delete=models.PROTECT, related_name='+')
    prepaid_account = models.ForeignKey('accounting.ChartAccount', on_delete=models.PROTECT, related_name='+')
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['entity', 'name'], name='reimbursement_payer_name')]

    def __str__(self):
        return f'{self.name} · {self.entity}'

    def clean(self):
        from .book_models import PropertyBooks
        from .models import FinancialAccount
        for field, kind in [('liability_account', 'liability'), ('prepaid_account', 'asset')]:
            account = getattr(self, field, None)
            if account and (account.account_type != kind or not account.is_active or FinancialAccount.objects.filter(ledger_account=account).exists()):
                raise ValidationError({field: 'Choose an active non-bank account of the appropriate type.'})
        if self.entity_id and self.liability_account_id:
            roles = ['payable', 'deposits', 'advances', 'credits']
            if any(PropertyBooks.objects.filter(entity_id=self.entity_id, **{role+'_id': self.liability_account_id}).exists() for role in roles):
                raise ValidationError({'liability_account': 'Use a separate reimbursement liability, distinct from property control accounts.'})
            others = type(self).objects.filter(entity_id=self.entity_id, liability_account_id=self.liability_account_id).exclude(pk=self.pk)
            if others.exists():
                raise ValidationError({'liability_account': 'Use a distinct liability account for this payer.'})
        if self.pk and self.settlements.exists():
            old = type(self).objects.get(pk=self.pk)
            if any(getattr(old, k) != getattr(self, k) for k in ['entity_id', 'liability_account_id', 'prepaid_account_id']):
                raise ValidationError('Recorded payer mappings cannot be changed; create a new mapping.')


class OnBehalfSettlement(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payment = models.OneToOneField('maintenance.VendorPayment', on_delete=models.PROTECT, related_name='on_behalf')
    payer = models.ForeignKey(ReimbursementPayer, on_delete=models.PROTECT, related_name='settlements')

    @property
    def reimbursed(self):
        return sum((r.amount for r in self.reimbursements.filter(status='recorded')), Decimal('0.00'))

    @property
    def outstanding(self):
        return self.payment.amount - self.reimbursed if self.payment.status == 'recorded' else Decimal('0.00')

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Payment funding records are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Payment funding records cannot be deleted.')


class BillReimbursement(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    settlement = models.ForeignKey(OnBehalfSettlement, on_delete=models.PROTECT, related_name='reimbursements')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    bank = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT)
    reference = models.CharField(max_length=180)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, default='recorded', choices=[('recorded', 'Recorded'), ('void', 'Void')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='bill_reimbursement_positive')]

    def save(self, *args, **kwargs):
        if not self._state.adding and not getattr(self, '_reviewed_void', False):
            raise ValidationError('Reimbursements are immutable; void with a reason.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Reimbursements cannot be deleted.')
