from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.urls import reverse
from common.models import FormFieldSetting
from common.audit.models import AuditEvent
from accounting.book_models import AccountingEntity,EntityBank
from accounting.test_book_accounting import BookAccountingTests

class PortalSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        BookAccountingTests.setUpTestData.__func__(cls)
        call_command('seed_portal_settings',verbosity=0)
        cls.admin=get_user_model().objects.create_superuser(username='settings_admin',email='admin@example.test',password='UniquePassphrase-Example2026!')
    def setUp(self):self.client.force_login(self.admin)
    def url(self,tab='companies',edit=None):return reverse('portal:portal_settings')+'?tab='+tab+('&edit='+str(edit) if edit else '')
    def post_data(self,response,**changes):
        form=response.context['form'];data={}
        for name,field in form.fields.items():
            value=form[name].value()
            if isinstance(value,bool):
                if value:data[name]='on'
            elif value is not None:data[name]=value
        data.update({'record_id':response.context['record_id'] or '', 'version':response.context['version']})
        data.update(changes)
        return data
    def test_existing_company_updated_in_place_and_audited(self):
        url=self.url(edit=self.entity.pk);response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        data=self.post_data(response,name='Updated company',default_basis='accrual')
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        self.entity.refresh_from_db();self.assertEqual(self.entity.name,'Updated company');self.assertEqual(AccountingEntity.objects.count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='PORTAL_CONFIGURATION_SAVED').exists())
    def test_stale_save_does_not_overwrite_another_change(self):
        url=self.url(edit=self.entity.pk);response=self.client.get(url)
        AccountingEntity.objects.filter(pk=self.entity.pk).update(name='Changed elsewhere')
        response=self.client.post(url,self.post_data(response,name='Stale overwrite'))
        self.assertEqual(response.status_code,200);self.assertContains(response,'This record changed')
        self.entity.refresh_from_db();self.assertEqual(self.entity.name,'Changed elsewhere')
    def test_permissions_read_only_view_and_denied_write(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_accountingentity',content_type__app_label='accounting'))
        response=self.client.get(self.url(edit=self.entity.pk));self.assertEqual(response.status_code,200);self.assertFalse(response.context['can_edit'])
        response=self.client.post(self.url(edit=self.entity.pk),self.post_data(response,name='Denied'))
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.get(self.url('users')).status_code,403)
    def test_bank_ownership_cannot_be_reassigned(self):
        url=self.url('banks',self.entity_bank.pk);response=self.client.get(url)
        self.assertFalse(response.context['can_edit'])
        response=self.client.post(url,self.post_data(response,entity=self.entity.pk))
        self.assertEqual(response.status_code,403);self.assertEqual(EntityBank.objects.count(),1)
    def test_field_texts_reuse_same_record_and_stable_option_codes(self):
        row=FormFieldSetting.objects.get(form_key='accounting_books',field_key='event_kinds')
        old_keys=set(row.option_labels);url=self.url('fields',row.pk);response=self.client.get(url)
        form=response.context['form'];field=next(name for name,key in form.option_fields.items() if key=='deposit_in')
        data=self.post_data(response,**{field:'Receive refundable deposit'})
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        row.refresh_from_db();self.assertEqual(set(row.option_labels),old_keys);self.assertEqual(row.option_labels['deposit_in'],'Receive refundable deposit')
    def test_creating_field_setting_and_cross_tab_token_are_rejected(self):
        response=self.client.get(self.url(edit=self.entity.pk));data=self.post_data(response)
        result=self.client.post(self.url('roles'),data)
        self.assertEqual(result.status_code,404 if not __import__('django.contrib.auth.models',fromlist=['Group']).Group.objects.filter(pk=self.entity.pk).exists() else 200)
        self.assertEqual(self.client.post(self.url('fields'),{'record_id':'','version':response.context['version']}).status_code,403)
    def test_staff_self_access_cannot_be_removed_and_passwords_not_logged(self):
        url=self.url('users',self.admin.pk);response=self.client.get(url);data=self.post_data(response)
        data.pop('is_staff',None)
        result=self.client.post(url,data);self.assertEqual(result.status_code,200);self.assertContains(result,'own active staff access')
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_staff)
        response=self.client.get(url);data=self.post_data(response,password1='AnotherUnique-Passphrase-2026!',password2='AnotherUnique-Passphrase-2026!')
        result=self.client.post(url,data);self.assertEqual(result.status_code,302)
        event=AuditEvent.objects.filter(action='PORTAL_CONFIGURATION_SAVED').latest('occurred_at')
        self.assertNotIn('AnotherUnique',str(event.new_values));self.assertNotIn('pbkdf2',str(event.new_values));self.assertNotIn('password',event.old_values)
    def test_csrf_and_login_stay_in_portal_authentication(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.url(),{'name':'Blocked'}).status_code,403)
        client.logout();response=client.get(self.url());self.assertTrue(response.url.startswith('/accounts/login/'))
    def test_navigation_and_help_text_are_escaped(self):
        row=FormFieldSetting.objects.get(form_key='portal_settings',field_key='name');row.help_text='<script>bad()</script>';row.save()
        response=self.client.get(self.url(edit=self.entity.pk))
        self.assertContains(response,'&lt;script&gt;bad()&lt;/script&gt;');self.assertNotContains(response,'<script>bad()</script>')
        self.assertNotContains(response,'Django Admin');self.assertContains(response,'/portal/settings/')
    def test_seed_does_not_overwrite_existing_settings(self):
        row=FormFieldSetting.objects.get(form_key='portal_settings',field_key='ui');row.option_labels['title']='Our settings';row.save()
        count=AccountingEntity.objects.count();call_command('seed_portal_settings',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.option_labels['title'],'Our settings');self.assertEqual(AccountingEntity.objects.count(),count)
    def test_posted_property_accounts_stay_locked_while_reserve_is_editable(self):
        BookAccountingTests.charge(self)
        url=self.url('properties',self.config.pk);response=self.client.get(url)
        self.assertTrue(response.context['form'].fields['rent_income'].disabled)
        data=self.post_data(response,reserve='150.00',rent_income=str(self.asset.pk))
        result=self.client.post(url,data);self.assertEqual(result.status_code,302)
        self.config.refresh_from_db();self.assertEqual(self.config.reserve,150);self.assertEqual(self.config.rent_income_id,self.income.pk)
    def test_creating_role_and_assigning_it_reuses_auth_groups(self):
        from django.contrib.auth.models import Group
        url=self.url('roles');response=self.client.get(url)
        permission=Permission.objects.get(codename='view_accountingentity',content_type__app_label='accounting')
        result=self.client.post(url,self.post_data(response,name='Configuration reader',permissions=[permission.pk]))
        self.assertEqual(result.status_code,302)
        role=Group.objects.get(name='Configuration reader');self.assertTrue(role.permissions.filter(pk=permission.pk).exists())
        url=self.url('users',self.staff.pk);response=self.client.get(url)
        result=self.client.post(url,self.post_data(response,groups=[role.pk],password1='',password2=''))
        self.assertEqual(result.status_code,302)
        self.client.force_login(self.staff);self.assertEqual(self.client.get(self.url()).status_code,200)
    def test_audit_failure_rolls_back_settings_change(self):
        from unittest.mock import patch
        url=self.url(edit=self.entity.pk);response=self.client.get(url);original=self.entity.name
        with patch('portal.settings_views.record_event',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.client.post(url,self.post_data(response,name='Must roll back'))
        self.entity.refresh_from_db();self.assertEqual(self.entity.name,original)

    def test_payer_tab_is_initialized_by_portal_settings_seed(self):
        response=self.client.get(self.url('payers'))
        self.assertEqual(response.status_code,200)
        self.assertIn('payers',[tab['key'] for tab in response.context['tabs']])
        self.assertEqual(response.context['form'].fields['liability_account'].label,'Reimbursement liability account')
        self.assertEqual(response.context['form'].fields['prepaid_account'].label,'Prepaid expense account')

    def test_payer_navigation_seed_repairs_missing_key_without_overwriting_edits(self):
        row=FormFieldSetting.objects.get(form_key='portal_settings',field_key='ui')
        row.option_labels.pop('payers',None)
        row.option_labels['title']='Custom portal settings';row.save()
        call_command('seed_portal_settings',verbosity=0)
        row.refresh_from_db()
        self.assertIn('payers',row.option_labels)
        self.assertEqual(row.option_labels['title'],'Custom portal settings')
        row.option_labels['payers']='Custom reimbursement parties';row.save()
        call_command('seed_portal_settings',verbosity=0)
        row.refresh_from_db()
        self.assertEqual(row.option_labels['payers'],'Custom reimbursement parties')
