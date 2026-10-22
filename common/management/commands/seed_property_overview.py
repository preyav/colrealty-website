from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

DEFAULTS = {
    'management_status':'Property Management Status','occupancy':'Occupancy',
    'active_leases':'Active Leases','open_maintenance':'Open Maintenance','details':'Property Details',
    'back':'← Back to Properties','edit_property':'Edit Property','address':'Address','unit':'Unit',
    'edit_unit':'Edit unit','add_unit':'+ Add Unit','units':'Units','property_type':'Property Type',
    'year':'Year Built','bedrooms':'Bedrooms','bathrooms':'Bathrooms · Full / Half','sqft':'Square Feet',
    'manager':'Property Manager','access_instructions':'Access & visit instructions','approval_limit':'Maintenance approval limit','no_image':'Primary image not available','image_field':'main_image_url',
    'occupied':'Occupied','vacant':'Vacant','unconfirmed':'Occupancy needs review','upcoming':'Upcoming lease',
    'not_configured':'Not configured','inactive':'Inactive account','cash_banking':'Cash & Banking',
    'configure':'Configure','cash':'Property posted cash','deposits':'Refundable deposits held',
    'advances':'Advance rent held','credits':'Client credits','payable':'Unpaid posted bills',
    'reimbursements':'Reimbursements payable','reserve':'Property reserve','available':'Available owner funds',
    'unavailable':'Pending review','provisional':'Provisional: accounting posting, bank reconciliation or property activation is incomplete. Available owner funds cannot yet be confirmed.',
    'cash_help_label':'Cash balance information','cash_help':'Property posted cash includes only this property’s cash-basis bank ledger entries as of today, across banks owned by its accounting entity. It is not the total shared bank balance or a live bank feed. Held funds, unpaid obligations and reserve reduce available owner funds.',
    'operating_bank':'Operating account','deposit_bank':'Deposit account',
    'setup_help':'Configure this property’s accounting entity and bank roles in Portal Settings → Property accounting. No bank is selected automatically.',
    'income_statement':'View Income Statement','maintenance':'Maintenance','new_request':'+ New Request',
    'view_all':'View All','no_requests':'No maintenance requests.','direct_work':'Work orders without a maintenance request',
    'all_work':'View all property work orders','vendor':'Assigned vendor','actual_cost':'Actual cost','bill':'Bill',
    'no_work':'No work orders yet.',
}

class Command(BaseCommand):
    def handle(self,*args,**options):
        row,created=FormFieldSetting.objects.get_or_create(form_key='property_overview',field_key='ui',defaults={'label':'Property overview','option_labels':DEFAULTS})
        if not created:
            row.option_labels={**DEFAULTS,**row.option_labels};row.save(update_fields=['option_labels'])
        for key,label in [('operating_bank','Operating account'),('deposit_bank','Deposit account')]:
            FormFieldSetting.objects.get_or_create(form_key='portal_settings',field_key=key,defaults={
                'label':label,'help_text':'Optional property bank role. Choose an existing bank owned by this property’s accounting entity. Existing transactions and their funding accounts are preserved.'})
        self.stdout.write('Property overview settings ready. No properties, bank assignments or transactions changed.')
