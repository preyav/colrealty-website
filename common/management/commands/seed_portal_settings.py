from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize Portal Settings wording without changing companies, roles, bank links or property accounts.'
    def handle(self,*args,**kwargs):
        ui={'title':'Settings','companies':'Companies & accounting','banks':'Bank account ownership','properties':'Property accounting','fields':'Field labels & options','users':'Staff access','roles':'Roles & permissions','payers':'Reimbursement payers',
            'add':'Add new','save':'Save changes','search':'Search','empty':'No records.','previous':'Previous','next':'Next','select_record':'Select a setting from the list to edit its labels, information and existing option values.','read_only':'This record is read-only for your access level or its accounting history.',
            'verified_email_help':'Existing sign-in emails use the account’s verified email-change process. This page does not bypass verification.','email_in_use':'This sign-in email already belongs to an account. Review the existing user instead of creating a duplicate.','saved':'Settings saved.','stale':'This record changed or the form expired. Reload the record before saving.','duplicate':'A record with these details already exists. Reload and review before trying again.',
            'classification':'Reporting classification','unclassified':'Unclassified','operating':'Operating','non_operating':'Non-operating','default_basis':'Default reporting basis','password_mismatch':'The passwords do not match.','self_access':'You cannot remove your own active staff access here.','last_admin':'Keep at least one active administrator with staff access.','banking':'Manage bank accounts in Banking','property_details':'Open Properties'}
        row,_=FormFieldSetting.objects.get_or_create(form_key='portal_settings',field_key='ui',defaults={'label':'Portal Settings wording','option_labels':ui})
        options=dict(row.option_labels)
        for key,value in ui.items():options.setdefault(key,value)
        if row.option_labels!=options:row.option_labels=options;row.save(update_fields=['option_labels'])
        fields={
            'name':('Name','The business or role name shown in COL360.'),
            'default_basis':('Default reporting basis','Default for this company’s Financials and General Ledger reports. Both reporting bases remain available.'),
            'is_active':('Active','Keep historical records while controlling whether this company or user is active.'),
            'entity':('Company / accounting entity','The company whose separate books own these property transactions or this bank account.'),
            'bank':('Bank account','Select an existing account from Banking. Saved ownership links cannot be reassigned.'),
            'property':('Property','Select the existing property. The property’s recorded transactions remain unchanged.'),
            'reserve':('Owner reserve','Amount to retain before calculating funds available for an owner distribution.'),
            'rent_income':('Rental income account','Income category for earned or collected rent, according to reporting basis.'),
            'receivable':('Tenant receivables account','Asset account for amounts owed by tenants.'),
            'liability_account':('Reimbursement liability account','Choose a distinct liability account for advances owed to this payer. Do not use tenant deposits, rent credits or vendor accounts payable.'),
            'prepaid_account':('Prepaid expense account','Choose a non-bank asset account used when a vendor payment precedes accrual recognition.'),
            'payable':('Vendor payables account','Liability account for unpaid approved vendor bills.'),
            'deposits':('Refundable deposit liability','Separate liability account for refundable client deposits.'),
            'advances':('Advance rent liability','Separate liability account for rent received before service in accrual books.'),
            'credits':('Unapplied client credit liability','Separate liability account for payments not yet allocated or classified.'),
            'owner_equity':('Owner equity account','Account used for owner contributions and distributions.'),
            'enabled':('Enable automatic rent posting','Enable only after reviewing the property’s accounting history and bank ownership. Existing history is not bulk-posted.'),
            'label':('Field label','Wording shown beside the field. Its stored identifier stays unchanged.'),
            'help_text':('Information text','Information shown with this field’s info icon.'),
            'username':('Username','Existing sign-in name. Changing it may change how this user signs in.'),
            'email':('Email','Enter a valid email address.'),
            'first_name':('First name',''), 'last_name':('Last name',''),
            'is_staff':('Staff portal access','Allows access to staff functions. Existing staff-only operational pages are not changed by this Settings update.'),
            'groups':('Roles','Assign existing permission groups. Role membership does not create a property-specific access boundary.'),
            'permissions':('Permissions','Existing application permissions granted to this role. Staff-access and administrator restrictions still apply.'),
            'password1':('New password','Required for a new user; leave blank to retain an existing password.'),
            'password2':('Confirm new password','Enter the same new password again.')}
        for key,(label,help_text) in fields.items():FormFieldSetting.objects.get_or_create(form_key='portal_settings',field_key=key,defaults={'label':label,'help_text':help_text})
        self.stdout.write(self.style.SUCCESS('Portal Settings wording initialized; existing records and labels preserved.'))

        row=FormFieldSetting.objects.get(form_key='portal_settings',field_key='default_basis')
        options=dict(row.option_labels)
        for key,label in [('cash','Cash basis'),('accrual','Accrual basis')]:options.setdefault(key,label)
        row.option_labels=options;row.save(update_fields=['option_labels'])
