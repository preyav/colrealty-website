import uuid,json,tempfile
from pathlib import Path
from io import StringIO
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.management import call_command,CommandError
from django.test import TestCase
from django.http import QueryDict
from .test_book_accounting import BookAccountingTests as Fixtures
from .models import ChartAccount
from .rent_models import RentCharge,RentReceipt,RentAllocation
from .rent_services import post_charge,entry_snapshot,edit_entry
from .book_services import post_rent_receipt
from .book_reports import account_balance
from .rent_forms import ChargeForm

class ChargeItemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Fixtures.setUpTestData.__func__(cls)
        cls.staff.is_superuser=True;cls.staff.save()
        call_command('seed_charge_itemization',verbosity=0)
        cls.utility=ChartAccount.objects.create(code='4901',name='Utility reimbursement',account_type='income',fund_type='operating')
    def prepare(self):
        c=RentCharge.objects.create(lease=self.lease,period_start=self.today,period_end=self.today,due_date=self.today,amount=Decimal('1857.16'),created_by=self.staff)
        items=[{'account_id':self.income.pk,'amount':'1800.00','description':'Rent'},{'account_id':self.utility.pk,'amount':'57.16','description':'Electricity'}]
        data={key:getattr(c,key) for key in ('period_start','period_end','due_date','amount','notes')};data['income_items']=items
        edit_entry(self.lease.pk,'charge',c.pk,data,entry_snapshot(c,'charge'),'Reviewed classification',self.staff);c.refresh_from_db()
        return c,items
    def test_cash_and_accrual_itemization_preserves_payment_dates_and_totals(self):
        c,items=self.prepare()
        for amount in ('1700.00','157.16'):
            r=RentReceipt.objects.create(lease=self.lease,received_date=self.today,amount=amount,payment_method='check',financial_account=self.bank,created_by=self.staff)
            RentAllocation.objects.create(receipt=r,charge=c,amount=amount);post_rent_receipt(r,self.staff)
            if amount=='1700.00':self.assertEqual(account_balance(self.entity,self.utility,self.today,self.property.pk,'cash'),0)
        for basis in ('cash','accrual'):
            self.assertEqual(account_balance(self.entity,self.utility,self.today,self.property.pk,basis),Decimal('57.16'))
            self.assertEqual(account_balance(self.entity,self.income,self.today,self.property.pk,basis),Decimal('1800.00'))
        count=self.entity.bookposting_set.count();post_rent_receipt(r,self.staff);self.assertEqual(self.entity.bookposting_set.count(),count)
        with self.assertRaises(ValidationError):edit_entry(self.lease.pk,'charge',c.pk,{'amount':c.amount},entry_snapshot(c,'charge'),'Cannot edit posted',self.staff)
    def test_form_widget_roundtrip_and_invalid_total(self):
        c,items=self.prepare();q=QueryDict('',mutable=True)
        q.update({'period_start':str(self.today),'period_end':str(self.today),'due_date':str(self.today),'amount':'1857.16'})
        for key,values in [('account',[str(self.income.pk),str(self.utility.pk)]),('amount',['1800','57.16']),('description',['Rent','Electricity'])]:q.setlist('income_items_'+key,values)
        form=ChargeForm(q);self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['income_items'],items)
        self.assertIn('Add income item',str(ChargeForm(initial={'income_items':items})['income_items']))
        q['amount']='1800';self.assertFalse(ChargeForm(q).is_valid())
    def test_wrong_account_rejected_before_charge_saved(self):
        from .charge_items import normalize_items
        with self.assertRaises(ValidationError):normalize_items([{'account_id':self.asset.pk,'amount':'10'}],Decimal('10'))
    def test_reviewed_command_preview_apply_repeat_and_posted_guard(self):
        c=RentCharge.objects.create(lease=self.lease,period_start=self.today,period_end=self.today,due_date=self.today,amount='100',created_by=self.staff)
        plan={'lease_id':self.lease.pk,'property_id':self.property.pk,'unit_number':self.unit.unit_number,'street_address':self.property.street_address,'reason':'Reviewed test classification','charges':[{'id':c.pk,'amount':'100','period_start':str(self.today),'period_end':str(self.today),'income_items':[{'account_id':self.utility.pk,'amount':'100','description':'Utility'}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';p.write_text(json.dumps(plan))
            call_command('classify_lease_charges',source=str(p),stdout=StringIO());c.refresh_from_db();self.assertEqual(c.income_items,[])
            call_command('classify_lease_charges',source=str(p),apply=True,actor_id=self.staff.pk,stdout=StringIO());c.refresh_from_db();self.assertEqual(c.income_items[0]['account_id'],self.utility.pk)
            out=StringIO();call_command('classify_lease_charges',source=str(p),apply=True,actor_id=self.staff.pk,stdout=out);self.assertIn('Already classified',out.getvalue())

    def test_due_date_default_uses_contract_day_not_late_day(self):
        from .rent_views import entry_defaults
        self.lease.contract_details={'rent_due_day':'1','late_charge_starts_on_day':'3'}
        self.lease.save()
        self.assertEqual(entry_defaults(self.lease,'charge',uuid.uuid4())['due_date'].day,1)

    def test_classification_guard_keeps_posted_source_unchanged(self):
        c,items=self.prepare()
        from .book_services import post_rent_charge
        post_rent_charge(c,self.staff)
        with self.assertRaises(ValidationError):
            data={key:getattr(c,key) for key in ('period_start','period_end','due_date','amount','notes')}
            data['income_items']=[]
            edit_entry(self.lease.pk,'charge',c.pk,data,entry_snapshot(c,'charge'),'Attempt reclassification',self.staff)
        c.refresh_from_db();self.assertEqual(c.income_items,items)
