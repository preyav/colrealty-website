import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from accounting.rent_services import post_charge,post_receipt,ledger_data,void_entry,apply_credit,portfolio_rent_data
from accounting.rent_models import RentCharge,RentReceipt,RentAllocation
from common.audit.models import AuditEvent
from properties.models import Property,PropertyUnit
from leasing.models import Lease


class RentPhase1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_rent_ledger',verbosity=0)
        call_command('seed_rent_workspace',verbosity=0)
        call_command('seed_lease_financials',verbosity=0)
        call_command('seed_lease_summary',verbosity=0)
        cls.actor=get_user_model().objects.create(username='rent_staff',is_staff=True,is_active=True)
        cls.other=get_user_model().objects.create(username='rent_nonstaff',is_staff=False,is_active=True)
        prop=Property.objects.create(street_address='Rent test property',management_status='active')
        unit=PropertyUnit.objects.create(property=prop,unit_number='1')
        cls.lease=Lease.objects.create(unit=unit,start_date=timezone.localdate()-timedelta(days=365),end_date=timezone.localdate()+timedelta(days=365),monthly_rent='2400',status='active')

    def charge(self,amount='2400',token=None,offset=0):
        start=timezone.localdate()+timedelta(days=offset)
        return post_charge(self.lease.pk,{'period_start':start,'period_end':start+timedelta(days=29),'due_date':start-timedelta(days=1),'amount':Decimal(amount),'notes':''},token or uuid.uuid4(),self.actor)

    def receipt(self,amount='1000',token=None):
        return post_receipt(self.lease.pk,{'received_date':timezone.localdate(),'amount':Decimal(amount),'payment_method':'check','reference':'Test payment','financial_account':None,'notes':''},token or uuid.uuid4(),self.actor)

    def test_partial_payment_and_audit(self):
        self.charge();self.receipt()
        data=ledger_data(self.lease)
        self.assertEqual(data['outstanding'],Decimal('1400'))
        self.assertEqual(data['overdue'],Decimal('1400'))
        self.assertEqual(data['credit'],0)
        self.assertEqual(AuditEvent.objects.filter(action__in=['RENT_CHARGE_POSTED','RENT_RECEIPT_RECORDED']).count(),2)

    def test_overpayment_becomes_credit_and_can_be_applied_later(self):
        self.charge();receipt=self.receipt('2600')
        self.assertEqual(ledger_data(self.lease)['credit'],Decimal('200'))
        self.charge(offset=30)
        apply_credit(self.lease.pk,receipt.pk,self.actor)
        apply_credit(self.lease.pk,receipt.pk,self.actor)
        self.assertEqual(ledger_data(self.lease)['credit'],0)
        self.assertEqual(ledger_data(self.lease)['outstanding'],Decimal('2200'))
        self.assertEqual(AuditEvent.objects.filter(action='RENT_CREDIT_APPLIED').count(),1)

    def test_entry_tokens_prevent_duplicate_charges_and_receipts(self):
        token=uuid.uuid4();self.charge(token=token);self.charge(token=token)
        token=uuid.uuid4();self.receipt(token=token);self.receipt(token=token)
        self.assertEqual(RentCharge.objects.count(),1)
        self.assertEqual(RentReceipt.objects.count(),1)
        self.assertEqual(RentAllocation.objects.count(),1)

    def test_overlapping_period_is_rejected(self):
        self.charge()
        with self.assertRaises(ValidationError):self.charge(offset=15)
        self.assertEqual(RentCharge.objects.count(),1)

    def test_void_receipt_restores_charge_and_preserves_history(self):
        self.charge();receipt=self.receipt()
        void_entry(self.lease.pk,'receipt',receipt.pk,'Incorrect entry',self.actor)
        self.assertEqual(ledger_data(self.lease)['outstanding'],Decimal('2400'))
        self.assertEqual(ledger_data(self.lease)['received'],0)
        self.assertEqual(RentAllocation.objects.count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='RENT_RECEIPT_VOIDED').exists())

    def test_paid_charge_cannot_be_voided(self):
        charge=self.charge();self.receipt()
        with self.assertRaises(ValidationError):void_entry(self.lease.pk,'charge',charge.pk,'Incorrect',self.actor)
        charge.refresh_from_db();self.assertEqual(charge.status,'posted')

    def test_void_unpaid_charge_removes_balance(self):
        charge=self.charge();void_entry(self.lease.pk,'charge',charge.pk,'Duplicate manual record',self.actor)
        self.assertEqual(ledger_data(self.lease)['outstanding'],0)
        self.assertEqual(RentCharge.objects.count(),1)

    def test_audit_failure_rolls_back_receipt_and_allocations(self):
        self.charge()
        with patch('accounting.rent_services.record_event',side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):self.receipt()
        self.assertFalse(RentReceipt.objects.exists());self.assertFalse(RentAllocation.objects.exists())
        self.assertEqual(ledger_data(self.lease)['outstanding'],Decimal('2400'))

    def test_nonstaff_cannot_post(self):
        with self.assertRaises(PermissionError):apply_credit(self.lease.pk,1,self.other)

    def test_allocation_is_scoped_to_lease(self):
        self.charge();receipt=self.receipt()
        lease=Lease.objects.create(unit=self.lease.unit,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30),monthly_rent='1000',status='active')
        with self.assertRaises(RentReceipt.DoesNotExist):apply_credit(lease.pk,receipt.pk,self.actor)
        self.assertEqual(ledger_data(lease)['received'],0)

    def test_portfolio_balance_matches_lease_balance(self):
        self.charge();self.receipt('2500')
        data=portfolio_rent_data()
        self.assertEqual(data['totals']['outstanding'],0)
        self.assertEqual(data['totals']['credit'],Decimal('100'))

    def test_future_receipt_is_rejected(self):
        data={'received_date':timezone.localdate()+timedelta(days=1),'amount':Decimal('10'),'payment_method':'cash','reference':'','financial_account':None,'notes':''}
        with self.assertRaises(ValidationError):post_receipt(self.lease.pk,data,uuid.uuid4(),self.actor)
        self.assertFalse(RentReceipt.objects.exists())

    def test_views_render_and_duplicate_browser_submit_posts_once(self):
        from django.urls import reverse
        self.client.force_login(self.actor)
        url=reverse('portal:rent_entry',kwargs={'lease_id':self.lease.pk,'kind':'charge'})
        response=self.client.get(url,follow=True)
        self.assertEqual(response.status_code,200)
        token=response.context['charge_token']
        today=timezone.localdate()
        payload={'entry_token':token,'period_start':str(today),'period_end':str(today+timedelta(days=29)),'due_date':str(today),'amount':'2400','notes':''}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.assertEqual(RentCharge.objects.count(),1)
        response=self.client.get(reverse('portal:rent_ledger',kwargs={'lease_id':self.lease.pk}))
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.endswith('#lease-financials'))

    def test_csrf_and_nonstaff_protect_payment_views(self):
        from django.urls import reverse
        from django.test import Client
        url=reverse('portal:rent_entry',kwargs={'lease_id':self.lease.pk,'kind':'receipt'})
        self.assertEqual(self.client.get(url).status_code,302)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.actor)
        self.assertEqual(csrf.get(url,follow=True).status_code,200)
        self.assertEqual(csrf.post(url,{'amount':'10'}).status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code,302)

    def test_void_view_cannot_target_a_different_lease(self):
        from django.urls import reverse
        charge=self.charge()
        other=Lease.objects.create(unit=self.lease.unit,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=90),monthly_rent='1000',status='active')
        self.client.force_login(self.actor)
        url=reverse('portal:rent_void',kwargs={'lease_id':other.pk,'kind':'charge','entry_id':charge.pk})
        self.assertEqual(self.client.get(url).status_code,404)

    def test_same_live_payment_reference_cannot_be_recorded_twice(self):
        self.receipt()
        with self.assertRaises(ValidationError):self.receipt()
        self.assertEqual(RentReceipt.objects.count(),1)

    def test_unified_defaults_and_editable_due_day(self):
        from django.urls import reverse
        self.lease.contract_details={'rent_due_day':'5'};self.lease.save()
        self.client.force_login(self.actor)
        response=self.client.get(reverse('portal:rent_entry',args=[self.lease.pk,'receipt']))
        charge=response.context['charge_form'];receipt=response.context['receipt_form']
        today=timezone.localdate()
        self.assertEqual(charge.initial['due_date'],today.replace(day=5))
        self.assertEqual(receipt.initial['received_date'],today)
        self.assertTrue(receipt.initial['reference'].startswith('RENT-'))
        self.assertContains(response,'rent-label-line')
        self.assertContains(response,'data-pending')
        self.assertContains(response,'data-excess')
        self.assertEqual(charge['due_date'].value(),today.replace(day=5))

    def test_receipt_defaults_use_outstanding_and_previous_method(self):
        from django.urls import reverse
        self.charge();self.receipt(amount='1000')
        self.client.force_login(self.actor)
        response=self.client.get(reverse('portal:rent_entry',args=[self.lease.pk,'receipt']))
        form=response.context['receipt_form']
        self.assertEqual(form.initial['amount'],Decimal('1400'))
        self.assertEqual(form.initial['payment_method'],self.lease.rent_receipts.first().payment_method)
        self.assertNotEqual(form.initial['reference'],self.lease.rent_receipts.first().reference)

    def test_invalid_payment_stays_on_combined_screen(self):
        from django.urls import reverse
        self.client.force_login(self.actor)
        page=self.client.get(reverse('portal:rent_entry',args=[self.lease.pk,'receipt']))
        response=self.client.post(reverse('portal:rent_entry',args=[self.lease.pk,'receipt']),
            {'entry_token':page.context['receipt_token'],'amount':'-10'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['receipt_form'].errors)
        self.assertContains(response,'financial-entry-page')
        self.assertEqual(response.context['kind'],'receipt')
        self.assertFalse(RentReceipt.objects.exists())

    def test_redesigned_lease_workspace_uses_recorded_balances(self):
        from django.template.loader import render_to_string
        for command in ['seed_lease_agreement_fields','seed_lease_document_fields','seed_lease_agreement_page','seed_lease_overview_polish','seed_lease_workspace','seed_rent_allocations','seed_rent_entry_actions','seed_property_financials']:
            call_command(command,verbosity=0)
        self.charge();self.receipt(amount='1000')
        from django.test import RequestFactory
        from django.urls import resolve,reverse
        request=RequestFactory().get(reverse('portal:lease_detail',args=[self.lease.pk]))
        request.user=self.actor;request.resolver_match=resolve(request.path)
        html=render_to_string('portal/lease_detail.html',{'lease':self.lease},request=request)
        from common.models import FormFieldSetting
        allocation_ui=FormFieldSetting.objects.get(form_key='rent_allocations',field_key='ui').option_labels
        property_ui=FormFieldSetting.objects.get(form_key='property_financials',field_key='ui').option_labels
        self.assertIn(allocation_ui['action'],html)
        self.assertIn(property_ui['income_statement'],html)
        self.assertIn('lease-workspace-columns',html)
        self.assertIn('lease-workspace-rail',html)
        self.assertIn('$1,400.00',html)
        self.assertIn('lease-agreement-history',html)
        self.assertIn('lease-maintenance-history',html)
        self.assertIn('lease-activity-history',html)
        self.assertEqual(ledger_data(self.lease)['outstanding'],Decimal('1400'))

    def test_financial_timeline_preserves_void_reversals(self):
        from accounting.lease_financials import financial_timeline
        charge=self.charge();receipt=self.receipt(amount='1000')
        timeline=financial_timeline(ledger_data(self.lease))
        self.assertEqual(timeline['balance'],Decimal('1400'))
        void_entry(self.lease.pk,'receipt',receipt.pk,'Correction',self.actor)
        timeline=financial_timeline(ledger_data(self.lease))
        self.assertEqual(timeline['balance'],Decimal('2400'))
        self.assertEqual(len(timeline['rows']),3)
        self.assertEqual(sum(row['reversal'] for row in timeline['rows']),1)

    def test_financial_entry_supporting_url_and_return_tab(self):
        from django.urls import reverse
        self.client.force_login(self.actor)
        url=reverse('portal:rent_entry',args=[self.lease.pk,'receipt'])
        page=self.client.get(url)
        self.assertEqual(page.status_code,200)
        response=self.client.post(url,{'entry_token':page.context['entry_token'],
            'received_date':str(timezone.localdate()),'amount':'100','payment_method':'check',
            'reference':'CHECK-NEW','notes':'Received','supporting_link':'https://drive.google.com/example'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.endswith('#lease-financials'))
        self.assertIn('https://drive.google.com/example',RentReceipt.objects.get(reference='CHECK-NEW').notes)

    def test_summary_seed_initializes_current_navigation_and_preserves_labels(self):
        from common.models import FormFieldSetting
        for key in ['lease-overview','documents','documents_title','requests_maintenance']:
            self.assertTrue(FormFieldSetting.objects.filter(form_key='lease_summary',field_key=key).exists())
        row=FormFieldSetting.objects.get(form_key='lease_summary',field_key='lease-overview')
        row.label='Custom lease overview';row.save()
        call_command('seed_lease_summary',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.label,'Custom lease overview')
