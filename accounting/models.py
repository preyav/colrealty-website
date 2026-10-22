from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings


class ChartAccount(models.Model):
    TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    cash_asset = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='subaccounts')
    fund_type = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "account_type"],
                name="accounting_unique_chart_name_per_type",
            )
        ]

    def clean(self):
        super().clean()
        from common.models import FormFieldSetting
        errors=FormFieldSetting.objects.get(form_key='chart_account_details',field_key='errors').option_labels
        if self.cash_asset and self.account_type!='asset':
            raise ValidationError({'cash_asset':errors['cash_type']})
        if self.parent_id:
            visited={self.pk} if self.pk else set()
            current=self.parent
            while current:
                if current.pk in visited:
                    raise ValidationError({'parent':errors['cycle']})
                visited.add(current.pk)
                current=current.parent if current.parent_id else None
            if self.parent.account_type!=self.account_type:
                raise ValidationError({'parent':errors['parent_type']})
        if self.pk:
            if self.journal_lines.exists() and ChartAccount.objects.only('account_type').get(pk=self.pk).account_type!=self.account_type:
                from .general_ledger import wording
                raise ValidationError({'account_type':wording()['posted_account_type']})
            if self.subaccounts.exclude(account_type=self.account_type).exists():
                raise ValidationError({'account_type':errors['children_type']})
            linked=FinancialAccount.objects.filter(ledger_account_id=self.pk).first()
            if linked:
                expected='liability' if linked.kind=='credit_card' else 'asset'
                if self.account_type!=expected:
                    raise ValidationError({'account_type':errors['linked_type']})

    def __str__(self):
        return f"{self.code} · {self.name}"


class FinancialAccount(models.Model):
    KIND_CHOICES = [
        ("bank", "Bank Account"),
        ("trust", "Trust Account"),
        ("cash", "Cash / Petty Cash"),
        ("credit_card", "Credit Card"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=150, unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    ledger_account = models.OneToOneField(
        ChartAccount,
        on_delete=models.PROTECT,
        related_name="financial_account",
    )
    institution_name = models.CharField(max_length=150, blank=True)
    account_last_four = models.CharField(max_length=4, blank=True)
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    opening_balance_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()
        if self.account_last_four and not self.account_last_four.isdigit():
            raise ValidationError({"account_last_four": "Enter exactly four digits."})
        if self.account_last_four and len(self.account_last_four) != 4:
            raise ValidationError({"account_last_four": "Enter exactly four digits."})
        if self.ledger_account_id:
            expected = "liability" if self.kind == "credit_card" else "asset"
            if self.ledger_account.account_type != expected:
                label = "liability" if self.kind == "credit_card" else "asset"
                raise ValidationError({
                    "ledger_account": f"This financial account must use a {label} chart account."
                })
            if not self.ledger_account.is_active:
                raise ValidationError({"ledger_account": "Select an active chart account."})

    def __str__(self):
        suffix = f" ••••{self.account_last_four}" if self.account_last_four else ""
        return f"{self.name}{suffix}"


class QuickBooksConnection(models.Model):
    ENVIRONMENT_CHOICES = [("sandbox", "Sandbox"), ("production", "Production")]

    realm_id = models.CharField(max_length=100, unique=True)
    company_name = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES)
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField()
    access_token_expires_at = models.DateTimeField()
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quickbooks_connections",
    )
    connected_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-connected_at"]

    def __str__(self):
        return self.company_name or self.realm_id


class QuickBooksVendorMapping(models.Model):
    connection = models.ForeignKey(
        QuickBooksConnection,
        on_delete=models.CASCADE,
        related_name="vendor_mappings",
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.CASCADE,
        related_name="quickbooks_mappings",
    )
    quickbooks_vendor_id = models.CharField(max_length=100)
    sync_token = models.CharField(max_length=50, blank=True)
    display_name = models.CharField(max_length=255)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor__company_name", "vendor__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "vendor"],
                name="accounting_unique_qb_vendor_mapping",
            ),
            models.UniqueConstraint(
                fields=["connection", "quickbooks_vendor_id"],
                name="accounting_unique_qb_vendor_id",
            ),
        ]

    def __str__(self):
        return f"{self.vendor} → QuickBooks {self.quickbooks_vendor_id}"


class QuickBooksBillMapping(models.Model):
    connection = models.ForeignKey(
        QuickBooksConnection,
        on_delete=models.PROTECT,
        related_name="bill_mappings",
    )
    invoice = models.OneToOneField(
        "maintenance.VendorInvoice",
        on_delete=models.PROTECT,
        related_name="quickbooks_bill_mapping",
    )
    quickbooks_bill_id = models.CharField(max_length=100)
    sync_token = models.CharField(max_length=50, blank=True)
    document_number = models.CharField(max_length=100)
    expense_account_id = models.CharField(max_length=100)
    expense_account_name = models.CharField(max_length=255)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_synced_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "quickbooks_bill_id"],
                name="accounting_unique_qb_bill_id",
            )
        ]

    def __str__(self):
        return f"{self.invoice} → QuickBooks Bill {self.quickbooks_bill_id}"


class QuickBooksPaymentMapping(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending synchronization"),
        ("synced", "Synchronized"),
        ("deleted", "Removed from QuickBooks"),
        ("error", "Synchronization error"),
    ]

    connection = models.ForeignKey(
        QuickBooksConnection,
        on_delete=models.PROTECT,
        related_name="payment_mappings",
    )
    payment = models.OneToOneField(
        "maintenance.VendorPayment",
        on_delete=models.PROTECT,
        related_name="quickbooks_payment_mapping",
    )
    bill_mapping = models.ForeignKey(
        QuickBooksBillMapping,
        on_delete=models.PROTECT,
        related_name="payment_mappings",
    )
    quickbooks_payment_id = models.CharField(max_length=100, blank=True)
    sync_token = models.CharField(max_length=50, blank=True)
    document_number = models.CharField(max_length=100)
    payment_account_id = models.CharField(max_length=100)
    payment_account_name = models.CharField(max_length=255)
    payment_account_type = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_synced_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "quickbooks_payment_id"],
                condition=~models.Q(quickbooks_payment_id=""),
                name="accounting_unique_qb_payment_id",
            )
        ]

    def __str__(self):
        return f"{self.payment} → QuickBooks Payment {self.quickbooks_payment_id or 'pending'}"

# Register the lease rent subledger models with the existing accounting app.
from .rent_models import RentCharge, RentReceipt, RentAllocation

from .journal_models import JournalEntry, JournalLine

from .book_models import AccountingEntity, PropertyBooks, EntityBank, BookPosting, BillAccounting, FundsEvent, BankReconciliation, BankClearance

from .reimbursement_models import ReimbursementPayer, OnBehalfSettlement, BillReimbursement

from .statement_preferences import IncomeStatementPreference
