from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='tenant_work',field_key='ui',defaults={'label':'Tenant-performed work','option_labels':{
            'title':'Tenant-performed work','tenant':'Tenant performing the work','agreed_cost':'Agreed total — time and materials','terms':'Approval, scope and reimbursement terms','document':'Written agreement / supporting link',
            'schedule_confirmed':'Tenant has confirmed the schedule','scheduled_for':'Confirmed start date and time','expected_completion':'Expected completion date and time','edit':'Record or update tenant work arrangement','save':'Save tenant work arrangement',
            'terms_help':'Record the agreed scope, approving owner, approval evidence and payment/reimbursement arrangement. Saving does not record completion, create a bill, make a payment or reduce rent.',
            'schedule_confirmed_help':'Leave unchecked until the tenant confirms. Unchecking clears any existing planned start and arrival window; original values remain in audit history.',
            'agreed_cost_help':'Agreed total including time and materials, not an actual expense or payment. Record actual cost when work is complete.',
            'expected_completion_help':'A confirmed plan only; this never records actual completion.',
            'unconfirmed':'Schedule not yet confirmed','financial_help':'Reimbursement remains pending separate review; no payment or rent credit is created here.',
            'no_tenant':'Link this request to the correct lease and tenant before recording tenant-performed work.',
            'actual_cost_required':'Confirm the actual tenant-work cost within the agreed amount before recording completion.',
            'start_required':'Enter the confirmed start time.','past_date':'A newly planned start cannot be in the past.','end_order':'Expected completion cannot precede the confirmed start.',
            'stale':'This work order changed. Refresh and review before saving.','locked':'This work order is in progress, completed or cancelled; arrangement changes require review.',
            'vendor_conflict':'Existing vendor activity must be resolved before assigning tenant-performed work. Nothing changed.',
            'approval_required':'The request must have its recorded approval before arranging tenant work.',
            'tenant_not_vendor':'This is tenant-performed work. Use its arrangement and actual completion workflow; do not create a vendor assignment or invoice.',
            'saved':'Tenant work arrangement saved and audited. No vendor, invoice, payment or rent credit created.'}})
        self.stdout.write('Tenant-work labels initialized; existing edits preserved.')

        FormFieldSetting.objects.get_or_create(form_key='work_assignment',field_key='ui',defaults={'label':'Work performed by','option_labels':{
            'title':'Work performed by','performer_kind':'Work performed by','tenant_kind':'Tenant','owner_kind':'Owner / DIY','owner':'Owner performing the work',
            'edit':'Record or update work arrangement','save':'Save work arrangement',
            'agreed_cost':'Agreed total / estimated materials cost',
            'agreed_cost_help':'For tenant work, enter the agreed time-and-materials total. For owner DIY, cost is optional; leave blank if unknown or enter zero for no cost. This does not create an expense or payment.',
            'financial_help':'No reimbursement, invoice, payment or rent credit is recorded by this arrangement. Any financial settlement is reviewed separately.',
            'no_tenant':'Link the property owner or the request lease and tenant before assigning work.',
            'owner_required':'Select an active owner linked to this property.','tenant_required':'Select a tenant linked to this request lease.','cost_required':'Enter the agreed total for tenant-performed work.',
            'tenant_not_vendor':'This work is assigned to a tenant or owner. Use the work arrangement and actual completion actions instead of vendor actions.',
            'saved':'Work arrangement saved and audited. No vendor, invoice, payment or rent credit created.'}})
