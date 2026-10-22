from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from common.models import FormFieldSetting
from .models import ChartAccount,FinancialAccount
from .forms import ChartAccountForm

class ChartAccountDetailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_accounting_workspace',verbosity=0)
        call_command('seed_chart_account_details',verbosity=0)
        cls.parent=ChartAccount.objects.create(code='1000',name='Assets',account_type='asset')
        cls.child=ChartAccount.objects.create(code='1010',name='Bank',account_type='asset',parent=cls.parent)

    def data(self,**changes):
        data={'name':'Cash account','code':'1020','account_type':'asset','cash_asset':True,
            'account_level':'subaccount','parent':self.parent.pk,'fund_type':'operating','description':'Notes','is_active':True}
        return {**data,**changes}

    def test_subaccount_fields_persist(self):
        form=ChartAccountForm(data=self.data())
        self.assertTrue(form.is_valid(),form.errors)
        account=form.save();account.refresh_from_db()
        self.assertEqual(account.parent,self.parent)
        self.assertFalse(account.cash_asset)
        self.assertEqual(account.fund_type,'operating')
        self.assertEqual(account.description,'Notes')

    def test_parent_required_and_type_must_match(self):
        form=ChartAccountForm(data=self.data(parent=''))
        self.assertFalse(form.is_valid());self.assertIn('parent',form.errors)
        form=ChartAccountForm(data=self.data(account_type='expense',cash_asset=False))
        self.assertFalse(form.is_valid());self.assertIn('parent',form.errors)

    def test_cash_flag_cannot_be_enabled_by_add_form_post(self):
        form=ChartAccountForm(data=self.data(account_type='income',account_level='parent',parent=''))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.save().cash_asset)

    def test_cycles_and_reclassifying_parent_are_blocked(self):
        self.parent.parent=self.child
        with self.assertRaises(ValidationError):self.parent.full_clean()
        self.parent.parent=None;self.parent.account_type='income'
        with self.assertRaises(ValidationError):self.parent.full_clean()

    def test_parent_level_clears_old_parent(self):
        form=ChartAccountForm(instance=self.child,data=self.data(name=self.child.name,code=self.child.code,account_level='parent'))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertIsNone(form.save().parent)

    def test_linked_bank_type_and_cash_flag_are_locked(self):
        FinancialAccount.objects.create(name='Operating bank',kind='bank',ledger_account=self.child)
        form=ChartAccountForm(instance=self.child,data=self.data(name=self.child.name,code=self.child.code,account_type='expense',cash_asset=False,account_level='parent'))
        self.assertTrue(form.fields['account_type'].disabled)
        self.assertTrue(form.fields['cash_asset'].disabled)
        self.assertTrue(form.is_valid(),form.errors)
        saved=form.save();self.assertEqual(saved.account_type,'asset');self.assertTrue(saved.cash_asset)

    def test_fund_options_are_editable_and_seed_preserves_them(self):
        row=FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='chart_fund_type')
        row.option_labels['reserve']='Reserve';row.save()
        call_command('seed_chart_account_details',verbosity=0)
        form=ChartAccountForm(data=self.data(fund_type='reserve'))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save().fund_type,'reserve')

    def test_direct_self_parent_not_allowed(self):
        self.parent.parent=self.parent
        with self.assertRaises(ValidationError):self.parent.full_clean()

    def test_cash_asset_visible_only_editing_assets_and_always_disabled(self):
        add=ChartAccountForm()
        self.assertFalse(add.cash_asset_visible)
        self.assertTrue(add.fields['cash_asset'].disabled)
        edit=ChartAccountForm(instance=self.child)
        self.assertTrue(edit.cash_asset_visible)
        self.assertTrue(edit.fields['cash_asset'].disabled)
        income=ChartAccount.objects.create(code='4000',name='Income',account_type='income')
        other=ChartAccountForm(instance=income)
        self.assertFalse(other.cash_asset_visible)
        self.assertTrue(other.fields['cash_asset'].disabled)

    def test_edit_preserves_cash_flag_when_checkbox_not_submitted(self):
        self.child.cash_asset=True;self.child.save()
        form=ChartAccountForm(instance=self.child,data=self.data(name=self.child.name,code=self.child.code,cash_asset=False))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertTrue(form.save().cash_asset)
