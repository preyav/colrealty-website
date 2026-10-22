"""Manual lease rent subledger. It does not initiate bank transactions."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class RentCharge(models.Model):
    lease = models.ForeignKey('leasing.Lease', on_delete=models.PROTECT, related_name='rent_charges')
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    income_items = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, default='posted')
    entry_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['due_date', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='rent_charge_positive'),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F('period_start')), name='rent_charge_period_order'),
            models.CheckConstraint(condition=models.Q(status__in=['posted','void']), name='rent_charge_valid_status'),
            models.UniqueConstraint(fields=['lease','period_start','period_end'], condition=models.Q(status='posted'), name='rent_charge_unique_live_period'),
        ]

    def __str__(self):
        return f'{self.lease_id} · {self.period_start}–{self.period_end} · {self.amount}'


class RentReceipt(models.Model):
    lease = models.ForeignKey('leasing.Lease', on_delete=models.PROTECT, related_name='rent_receipts')
    received_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_method = models.CharField(max_length=40)
    reference = models.CharField(max_length=150, blank=True)
    financial_account = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT, null=True, blank=True, related_name='rent_receipts')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, default='recorded')
    entry_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_date', '-pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='rent_receipt_positive'),
            models.CheckConstraint(condition=models.Q(status__in=['recorded','void']), name='rent_receipt_valid_status'),
            models.UniqueConstraint(fields=['lease','payment_method','reference'], condition=models.Q(status='recorded') & ~models.Q(reference=''), name='rent_receipt_unique_live_reference'),
        ]

    def __str__(self):
        return f'{self.lease_id} · {self.received_date} · {self.amount}'


class RentAllocation(models.Model):
    receipt = models.ForeignKey(RentReceipt, on_delete=models.PROTECT, related_name='allocations')
    charge = models.ForeignKey(RentCharge, on_delete=models.PROTECT, related_name='allocations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='rent_allocation_positive'),
            models.UniqueConstraint(fields=['receipt','charge'], name='rent_allocation_unique_pair'),
        ]
