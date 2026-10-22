import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from .test_general_ledger import GeneralLedgerTests
from .models import ChartAccount,FinancialAccount
from .book_models import AccountingEntity,PropertyBooks,EntityBank,BookPosting,FundsEvent,BankClearance
from .book_services import record_funds,post_rent_receipt,post_bill,post_bill_payment,void_bill_payment
from .book_reports import account_balance,owner_funds,coverage
from .rent_services import post_charge,post_receipt,ledger_data,void_entry,edit_entry,entry_snapshot
from .general_ledger import ledger_report,post_journal,reverse_journal
from .financials import financial_report,month_start
from .bank_services import reconcile,bank_lines
from .journal_models import JournalLine
from leasing.models import Lease

class BookAccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        GeneralLedgerTests.setUpTestData.__func__(cls)
        for cmd in ['seed_rent_workspace','seed_lease_financials','seed_financials','seed_accounting_books']:call_command(cmd,verbosity=0)
        cls.entity=AccountingEntity.objects.create(name='Test entity')
        cls.bank=FinancialAccount.objects.create(name='Test bank',kind='trust',ledger_account=cls.asset)
        cls.entity_bank=EntityBank.objects.create(entity=cls.entity,bank=cls.bank)
        roles={}
        for code,role,kind in [('1200','receivable','asset'),('2100','payable','liability'),('2200','deposits','liability'),('2300','advances','liability'),('2400','credits','liability'),('3200','owner_equity','equity')]:
            roles[role]=ChartAccount.objects.create(code=code,name=role,account_type=kind)
        cls.config=PropertyBooks.objects.create(property=cls.property,entity=cls.entity,enabled=True,rent_income=cls.income,**roles)
        cls.today=timezone.localdate()
        cls.lease=Lease.objects.create(unit=cls.unit,start_date=cls.today-timedelta(days=400),end_date=cls.today+timedelta(days=400),monthly_rent='2400',status='active')
    def charge(self,start=None):
        start=start or month_start(self.today,0)
        return post_charge(self.lease.pk,{'period_start':start,'period_end':month_start(start,1)-timedelta(days=1),'due_date':start+timedelta(days=2),'amount':Decimal('2400'),'notes':''},uuid.uuid4(),self.staff)
    def receipt(self,amount='2400',date=None):
        return post_receipt(self.lease.pk,{'amount':Decimal(amount),'received_date':date or self.today,'payment_method':'check','reference':str(uuid.uuid4()),'financial_account':self.bank,'notes':''},uuid.uuid4(),self.staff)
    def funds(self,kind,amount='100',**kwargs):
        return record_funds({'property':self.property,'lease':self.lease,'kind':kind,'date':self.today,'amount':Decimal(amount),'bank':self.bank,'reference':str(uuid.uuid4()),'notes':'',**kwargs},uuid.uuid4(),self.staff)
    def balance(self,role,basis='accrual',date=None):
        account=self.income if role=='income' else getattr(self.config,role)
        return account_balance(self.entity,account,date or self.today,self.property.pk,basis)
    def test_late_payment_recognized_in_different_months_without_double_count(self):
        self.charge(month_start(self.today,-1));receipt=self.receipt()
        self.assertEqual(self.balance('income','cash'),2400);self.assertEqual(self.balance('income'),2400)
        cash=financial_report({'period':'three','scope':'property','property':self.property,'entity':self.entity,'basis':'cash'},self.today)['properties'][0]
        accrual=financial_report({'period':'three','scope':'property','property':self.property,'entity':self.entity,'basis':'accrual'},self.today)['properties'][0]
        self.assertEqual(cash['net'],[0,0,2400]);self.assertEqual(accrual['net'],[0,2400,0])
        count=BookPosting.objects.count();post_rent_receipt(receipt,self.staff);self.assertEqual(BookPosting.objects.count(),count)
        for posting in BookPosting.objects.all():
            self.assertEqual(sum((x.debit-x.credit for x in posting.journal.lines.all()),Decimal('0')),0)
    def test_early_payment_is_advance_liability_until_service_period(self):
        self.charge(self.today);self.receipt(date=self.today-timedelta(days=1))
        self.assertEqual(self.balance('income','cash',self.today-timedelta(days=1)),2400)
        self.assertEqual(self.balance('income','accrual',self.today-timedelta(days=1)),0)
        self.assertEqual(self.balance('advances',date=self.today-timedelta(days=1)),2400)
        self.assertEqual(self.balance('advances'),0);self.assertEqual(self.balance('receivable'),0)
    def test_refundable_deposit_is_never_rental_income(self):
        event=self.funds('deposit_in','1000')
        self.assertEqual(self.balance('deposits'),1000);self.assertEqual(self.balance('income','cash'),0)
        self.funds('deposit_refund','200',source=event)
        self.assertEqual(self.balance('deposits'),800)
        with self.assertRaises(ValidationError):self.funds('deposit_refund','900',source=event)
    def test_advance_receipt_application_and_refund_are_separate(self):
        event=self.funds('advance_in','1000');charge=self.charge()
        self.funds('advance_apply','600',source=event,charge=charge,bank=None)
        self.assertEqual(ledger_data(self.lease)['outstanding'],1800)
        self.funds('advance_refund','400',source=event)
        self.assertEqual(self.balance('advances'),0);self.assertEqual(self.balance('income','cash'),600)
    def test_credit_refund_and_charge_credit(self):
        receipt=self.receipt('500');self.funds('credit_refund','200',receipt=receipt)
        self.assertEqual(ledger_data(self.lease)['credit'],300);self.assertEqual(self.balance('credits'),300)
        with self.assertRaises(ValidationError):self.funds('credit_refund','400',receipt=receipt)
        charge=self.charge();self.funds('rent_credit','200',charge=charge,bank=None)
        self.assertEqual(ledger_data(self.lease)['outstanding'],2200)
        self.assertEqual(self.balance('income'),2200)
    def test_void_payment_reverses_both_books_and_keeps_originals(self):
        self.charge();receipt=self.receipt()
        original=BookPosting.objects.count()
        void_entry(self.lease.pk,'receipt',receipt.pk,'Duplicate',self.staff)
        self.assertEqual(self.balance('income','cash'),0);self.assertEqual(self.balance('income'),2400)
        self.assertEqual(self.balance('receivable'),2400)
        self.assertGreater(BookPosting.objects.count(),original)
        with self.assertRaises(ValidationError):
            edit_entry(self.lease.pk,'charge',self.lease.rent_charges.first().pk,{},entry_snapshot(self.lease.rent_charges.first(),'charge'),'Change',self.staff)
    def test_cross_entity_bank_and_property_remapping_are_rejected(self):
        other=AccountingEntity.objects.create(name='Other entity')
        EntityBank.objects.filter(pk=self.entity_bank.pk).update(entity=other)
        with self.assertRaises(ValidationError):self.receipt()
        self.assertEqual(self.lease.rent_receipts.count(),0)
        EntityBank.objects.filter(pk=self.entity_bank.pk).update(entity=self.entity)
        self.charge();self.config.entity=other
        with self.assertRaises(ValidationError):self.config.full_clean()
    def test_manual_books_do_not_sum_cash_and_accrual_and_reverse_together(self):
        journal=post_journal({'entity':self.entity,'basis':'both','date':self.today,'memo':'Reviewed opening','property':self.property,'unit':None,'fund_type':''},[{'account':self.asset,'debit':100,'credit':0},{'account':self.config.owner_equity,'debit':0,'credit':100}],uuid.uuid4(),self.staff)
        for basis in ['cash','accrual']:
            report=ledger_report({'start':self.today,'end':self.today,'entity':self.entity,'basis':basis})
            self.assertEqual(report['debit'],100);self.assertEqual(report['credit'],100)
        reverse_journal(journal.pk,self.today,'Correction',uuid.uuid4(),self.staff)
        self.assertEqual(account_balance(self.entity,self.asset,self.today,basis='cash'),0)
        self.assertEqual(account_balance(self.entity,self.asset,self.today,basis='accrual'),0)
    def test_bank_reconciliation_and_finalized_period_lock(self):
        self.funds('deposit_in','100')
        line=bank_lines(self.entity_bank,self.today).get()
        with self.assertRaises(ValidationError):reconcile(self.entity_bank.pk,self.today,self.today,Decimal('0'),Decimal('99'),[line.pk],self.staff,True)
        preview=reconcile(self.entity_bank.pk,self.today,self.today,Decimal('0'),Decimal('100'),[line.pk],self.staff)
        self.assertEqual(preview['difference'],0)
        final=reconcile(self.entity_bank.pk,self.today,self.today,Decimal('0'),Decimal('100'),[line.pk],self.staff,True)
        self.assertEqual(final.status,'final');self.assertEqual(BankClearance.objects.count(),1)
        with self.assertRaises(ValidationError):self.funds('deposit_in','100')
        self.assertEqual(FundsEvent.objects.count(),1)
    def test_owner_funds_exclude_client_liabilities_and_require_review(self):
        self.funds('deposit_in','1000')
        row=owner_funds(self.config)
        self.assertEqual(row['cash'],1000);self.assertEqual(row['provisional'],0);self.assertEqual(row['available'],0)
        self.funds('owner_in','500')
        self.assertEqual(owner_funds(self.config)['provisional'],500)
        with self.assertRaises(ValidationError):self.funds('owner_out','100')
    def test_default_cash_and_operations_access(self):
        self.client.force_login(self.staff)
        response=self.client.get(reverse('portal:finance_dashboard'))
        self.assertEqual(response.context['form'].data['basis'],'cash')
        response=self.client.get(reverse('portal:accounting_operations'))
        self.assertEqual(response.status_code,200);self.assertContains(response,'Bank reconciliation')
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse('portal:accounting_operations')).status_code,302)
    def test_seed_and_review_do_not_change_existing_sources(self):
        from io import StringIO
        self.config.enabled=False;self.config.save();charge=self.charge()
        before=charge.amount
        call_command('seed_accounting_books',verbosity=0)
        call_command('review_accounting_books',stdout=StringIO())
        charge.refresh_from_db();self.assertEqual(charge.amount,before);self.assertEqual(BookPosting.objects.count(),0)
    def bill(self):
        from maintenance.models import WorkOrder,VendorInvoice
        from vendors.models import Vendor
        from .book_models import BillAccounting
        work=WorkOrder.objects.create(unit=self.unit,title='Verified repair',description='Repair')
        vendor=Vendor.objects.create(name='Test vendor')
        invoice=VendorInvoice.objects.create(work_order=work,vendor=vendor,amount=Decimal('300'),status='approved',invoice_date=month_start(self.today,-1),due_date=self.today)
        expense=ChartAccount.objects.create(code='5900',name='Test repair expense',account_type='expense')
        BillAccounting.objects.create(invoice=invoice,expense_account=expense,service_start=month_start(self.today,-1),service_end=month_start(self.today,0)-timedelta(days=1),recognition_date=month_start(self.today,-1))
        return invoice,expense
    def test_bill_service_period_partial_payment_and_void(self):
        from maintenance.models import VendorPayment
        invoice,expense=self.bill();post_bill(invoice,self.staff)
        self.assertEqual(self.balance('payable'),300)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='cash'),0)
        payment=VendorPayment.objects.create(invoice=invoice,amount=Decimal('100'),payment_date=self.today,payment_method='check',financial_account=self.bank,recorded_by=self.staff)
        post_bill_payment(payment,self.staff)
        self.assertEqual(self.balance('payable'),200)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='cash'),100)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='accrual'),300)
        void_bill_payment(payment,'Duplicate',self.staff)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='cash'),0);self.assertEqual(self.balance('payable'),300)
    def test_vendor_credit_and_actual_refund_have_different_dates_and_effects(self):
        from maintenance.models import VendorPayment
        invoice,expense=self.bill();payment=VendorPayment.objects.create(invoice=invoice,amount=Decimal('300'),payment_date=self.today,payment_method='check',financial_account=self.bank,recorded_by=self.staff)
        post_bill_payment(payment,self.staff)
        self.funds('bill_credit','50',invoice=invoice,bank=None,lease=None)
        self.assertEqual(invoice.outstanding_amount,-50);self.assertEqual(self.balance('payable'),-50)
        self.funds('bill_refund','50',invoice=invoice,lease=None)
        self.assertEqual(invoice.outstanding_amount,0);self.assertEqual(self.balance('payable'),0)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='cash'),250)
        self.assertEqual(account_balance(self.entity,expense,self.today,basis='accrual'),250)
    def test_missing_bill_service_details_and_legacy_journals_require_review(self):
        invoice,expense=self.bill();invoice.book_details.delete()
        with self.assertRaises(ValidationError):post_bill(invoice,self.staff)
        self.assertEqual(BookPosting.objects.count(),0)
        self.assertIn('bill:'+str(invoice.pk),coverage(self.config)['missing'])
    def test_entity_filter_cannot_combine_other_property_books(self):
        from .financials import FinancialFilter
        form=FinancialFilter({'entity':str(self.entity.pk),'scope':'property:'+str(self.other_property.pk),'period':'three','basis':'cash'})
        self.assertFalse(form.is_valid());self.assertIn('scope',form.errors)
    def test_paid_rent_refund_keeps_allocation_history_and_no_new_ar(self):
        charge=self.charge();receipt=self.receipt()
        self.funds('rent_refund','100',receipt=receipt,charge=charge)
        ledger=ledger_data(self.lease)
        self.assertEqual(ledger['outstanding'],0);self.assertEqual(ledger['charged'],2300)
        self.assertEqual(self.balance('income','cash'),2300);self.assertEqual(self.balance('income','accrual'),2300)
        self.assertEqual(receipt.allocations.count(),1)
        with self.assertRaises(ValidationError):self.funds('rent_refund','2400',receipt=receipt,charge=charge)
    def test_posted_entry_cannot_void_when_book_setup_is_disabled(self):
        self.charge();receipt=self.receipt();self.config.enabled=False;self.config.save()
        with self.assertRaises(ValidationError):void_entry(self.lease.pk,'receipt',receipt.pk,'Correction',self.staff)
        receipt.refresh_from_db();self.assertEqual(receipt.status,'recorded')
    def test_rent_reconciliation_includes_client_funds(self):
        from common.management.commands.reconcile_lease_rent import reconcile as rent_reconcile
        charge=self.charge();advance=self.funds('advance_in','100')
        self.funds('advance_apply','100',source=advance,charge=charge,bank=None)
        report=rent_reconcile(self.lease,self.today)
        self.assertEqual(report['summary']['net_due_through_date'],2300)
        self.assertEqual(report['summary']['client_funds_applied_through_date'],100)
    def test_legacy_assignment_preserves_original_journal_and_does_not_copy(self):
        from .book_services import assign_legacy
        journal=post_journal({'date':self.today,'memo':'Existing verified receipt','property':self.property,'unit':self.unit,'fund_type':''},[{'account':self.asset,'debit':100,'credit':0},{'account':self.income,'debit':0,'credit':100}],uuid.uuid4(),self.staff,book_internal=True)
        values=list(journal.lines.values_list('account_id','debit','credit'))
        posting=assign_legacy(journal.pk,self.entity,'cash',self.staff)
        self.assertEqual(posting.journal_id,journal.pk)
        self.assertEqual(values,list(journal.lines.values_list('account_id','debit','credit')))
        self.assertEqual(self.balance('income','cash'),100);self.assertEqual(self.balance('income','accrual'),0)
        with self.assertRaises(ValidationError):assign_legacy(journal.pk,self.entity,'accrual',self.staff)
    def test_funds_audit_failure_rolls_back_both_books_and_event(self):
        from unittest.mock import patch
        with patch('accounting.book_services.record_event',side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):self.funds('deposit_in','100')
        self.assertEqual(FundsEvent.objects.count(),0);self.assertEqual(BookPosting.objects.count(),0)
