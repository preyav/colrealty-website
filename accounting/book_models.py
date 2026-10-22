"""Entity-scoped books. Source transactions remain in their original subledgers."""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

BASIS=[('cash','Cash'),('accrual','Accrual')]

class AccountingEntity(models.Model):
    name=models.CharField(max_length=180,unique=True)
    default_basis=models.CharField(max_length=10,choices=BASIS,default='cash')
    is_active=models.BooleanField(default=True)
    def __str__(self):return self.name

class PropertyBooks(models.Model):
    property=models.OneToOneField('properties.Property',on_delete=models.PROTECT,related_name='books')
    entity=models.ForeignKey(AccountingEntity,on_delete=models.PROTECT)
    operating_bank=models.ForeignKey('accounting.FinancialAccount',null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    deposit_bank=models.ForeignKey('accounting.FinancialAccount',null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    enabled=models.BooleanField(default=False)
    reserve=models.DecimalField(max_digits=14,decimal_places=2,default=Decimal('0'))
    rent_income=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    receivable=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    payable=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    deposits=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    advances=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    credits=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    owner_equity=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='+')
    def clean(self):
        roles={'rent_income':'income','receivable':'asset','payable':'liability','deposits':'liability','advances':'liability','credits':'liability','owner_equity':'equity'}
        for role in ['operating_bank','deposit_bank']:
            bank=getattr(self,role,None)
            if bank and (bank.kind=='credit_card' or not EntityBank.objects.filter(entity_id=self.entity_id,bank=bank).exists()):
                raise ValidationError({role:'Select a bank owned by this property accounting entity.'})
        ids=[]
        for role,kind in roles.items():
            if getattr(self,role+'_id'):
                account=getattr(self,role);ids.append(account.pk)
                if account.account_type!=kind or not account.is_active:raise ValidationError({role:'Select an active account of type '+kind+'.'})
        if len(set(ids))!=len(ids):raise ValidationError('Each control account must be distinct.')
        if self.reserve<0:raise ValidationError({'reserve':'Reserve must not be negative.'})
        if self.pk:
            prior=type(self).objects.get(pk=self.pk)
            if BookPosting.objects.filter(journal__property_id=prior.property_id).exists():
                for field in ['property_id','entity_id']+[role+'_id' for role in roles]:
                    if getattr(prior,field)!=getattr(self,field):raise ValidationError('Posted property books cannot be remapped; use a reviewed transfer journal.')
    def __str__(self):return str(self.property)+' · '+str(self.entity)

class EntityBank(models.Model):
    entity=models.ForeignKey(AccountingEntity,on_delete=models.PROTECT)
    bank=models.OneToOneField('accounting.FinancialAccount',on_delete=models.PROTECT,related_name='entity_book')
    def clean(self):
        if self.bank_id and self.bank.kind=='credit_card':raise ValidationError('Bank reconciliation requires a bank or cash account.')
        if self.pk:
            old=type(self).objects.get(pk=self.pk)
            if old.entity_id!=self.entity_id or old.bank_id!=self.bank_id:raise ValidationError('Bank ownership mappings cannot be reassigned. Create a separate bank account.')
    def __str__(self):return str(self.entity)+' · '+str(self.bank)

class BookPosting(models.Model):
    journal=models.OneToOneField('accounting.JournalEntry',on_delete=models.PROTECT,related_name='book_posting')
    entity=models.ForeignKey(AccountingEntity,on_delete=models.PROTECT)
    basis=models.CharField(max_length=10,choices=BASIS)
    source_key=models.CharField(max_length=180)
    snapshot=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['entity','basis','source_key'],name='books_unique_source_basis')]
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValidationError('Posting links are immutable.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError('Posting links are immutable.')

class BillAccounting(models.Model):
    invoice=models.OneToOneField('maintenance.VendorInvoice',on_delete=models.PROTECT,related_name='book_details')
    expense_account=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT)
    service_start=models.DateField()
    service_end=models.DateField()
    recognition_date=models.DateField()
    def clean(self):
        if self.service_end and self.service_start and self.service_end<self.service_start:raise ValidationError('Service period end precedes start.')
        if self.expense_account_id and (self.expense_account.account_type!='expense' or not self.expense_account.is_active):raise ValidationError('Select an active expense account.')
        if self.pk and BookPosting.objects.filter(source_key='bill:'+str(self.invoice_id)).exists():
            old=type(self).objects.get(pk=self.pk)
            if any(getattr(old,k)!=getattr(self,k) for k in ['invoice_id','expense_account_id','service_start','service_end','recognition_date']):raise ValidationError('Posted bill details are immutable.')

class FundsEvent(models.Model):
    KINDS=[(x,x.replace('_',' ').title()) for x in ['deposit_in','credit_to_deposit','deposit_refund','advance_in','advance_apply','advance_refund','deposit_apply','credit_refund','rent_credit','owner_in','owner_out','bill_credit','bill_refund','rent_refund']]
    token=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    property=models.ForeignKey('properties.Property',on_delete=models.PROTECT)
    lease=models.ForeignKey('leasing.Lease',null=True,blank=True,on_delete=models.PROTECT)
    kind=models.CharField(max_length=30,choices=KINDS)
    date=models.DateField()
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    bank=models.ForeignKey('accounting.FinancialAccount',null=True,blank=True,on_delete=models.PROTECT)
    source=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='applications')
    receipt=models.ForeignKey('accounting.RentReceipt',null=True,blank=True,on_delete=models.PROTECT,related_name='fund_events')
    invoice=models.ForeignKey('maintenance.VendorInvoice',null=True,blank=True,on_delete=models.PROTECT,related_name='fund_events')
    charge=models.ForeignKey('accounting.RentCharge',null=True,blank=True,on_delete=models.PROTECT,related_name='fund_events')
    reference=models.CharField(max_length=180)
    notes=models.TextField(blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='fund_event_amount_positive')]
    def get_kind_display(self):
        from common.models import FormFieldSetting
        row=FormFieldSetting.objects.filter(form_key='accounting_books',field_key='event_kinds').first()
        return row.option_labels.get(self.kind,self.kind) if row else dict(self.KINDS).get(self.kind,self.kind)
    def __str__(self):return f'{self.get_kind_display()} · {self.date} · {self.property} · {self.amount} · {self.reference}'
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValidationError('Funds events are immutable; correct with a separate reviewed event.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError('Funds events cannot be deleted.')

class BankReconciliation(models.Model):
    entity_bank=models.ForeignKey(EntityBank,on_delete=models.PROTECT)
    statement_start=models.DateField()
    statement_end=models.DateField()
    opening_balance=models.DecimalField(max_digits=14,decimal_places=2)
    closing_balance=models.DecimalField(max_digits=14,decimal_places=2)
    status=models.CharField(max_length=12,default='draft',choices=[('draft','Draft'),('final','Final')])
    finalized_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT)
    finalized_at=models.DateTimeField(null=True,blank=True)
    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.get(pk=self.pk).status=='final':raise ValidationError('Final bank reconciliations are locked.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError('Reconciliation history cannot be deleted.')

class BankClearance(models.Model):
    reconciliation=models.ForeignKey(BankReconciliation,on_delete=models.PROTECT,related_name='clearances')
    line=models.OneToOneField('accounting.JournalLine',on_delete=models.PROTECT,related_name='bank_clearance')
    def save(self,*args,**kwargs):
        if self.reconciliation.status=='final':raise ValidationError('Final bank reconciliations are locked.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        if self.reconciliation.status=='final':raise ValidationError('Final bank reconciliations are locked.')
        return super().delete(*args,**kwargs)
