from django.core.management.base import BaseCommand
from common.models import FormFieldSetting


class Command(BaseCommand):
    help='Initialize editable navigation and property-register labels without changing business records.'
    def handle(self,*args,**kwargs):
        groups={
            'portal_navigation':{'leasing':'Leasing','rentals':'Rentals','properties':'Properties','leases':'Leases','tenants':'Tenants','owners':'Owners','outstanding':'Outstanding balances','maintenance':'Maintenance','vendors':'Vendors','requests':'Maintenance requests','work_orders':'Work orders','inspections':'Property inspections','assets':'Inventory and assets'},
            'property_registers':{
                'ui':{'add':'Add record','edit':'Edit','save':'Save changes','cancel':'Cancel','search':'Search','clear':'Clear','all':'All','empty':'No records found.','saved':'Record saved.','property':'Property','unit':'Unit','title':'Name / title','status':'Status','notes':'Notes / findings','document_link':'Document link','scheduled_on':'Scheduled date','completed_on':'Completed date','inspection_type':'Inspection type','assigned_to':'Assigned staff member','quantity':'Quantity','manufacturer':'Manufacturer','model_number':'Model number','serial_number':'Serial number','installed_on':'Installation date','warranty_until':'Warranty expires','actions':'Actions','stale':'This record changed. Reload before saving your changes.','unit_load_error':'Unable to load units. Select the property again before saving.','unit_mismatch':'Select a unit belonging to this property.','completed_required':'Enter the completion date for a completed inspection.','quantity_positive':'Quantity must be at least one.','inspections_help':'Schedule inspections and retain findings and links to inspection reports. Record any resulting repair as a maintenance request.','assets_help':'Track property equipment and inventory, locations, serial numbers and warranty dates. These records do not create accounting entries.','document_help':'Paste a Google Drive or other document link. Document access is controlled by its provider.','unit_help':'Leave blank for property-level records. Only units saved under the selected property are available.','notes_help':'Keep findings, condition details and follow-up information here.','property_help':'Choose the property this record belongs to.','scheduled_help':'The planned inspection date.','completed_help':'The actual completion date; required when marked completed.','assigned_help':'The staff member responsible for this inspection.','type_help':'The purpose of the inspection.','status_help':'Current progress or availability.','title_help':'A short descriptive name for this record.','quantity_help':'Number of identical items represented by this record.','manufacturer_help':'The maker shown on the equipment label.','model_help':'The equipment model identifier.','serial_help':'The serial identifier for this item.','installed_help':'Installation date, if known.','warranty_help':'Warranty expiration date, if known.'},
                'inspection_status':{'scheduled':'Scheduled','in_progress':'In progress','completed':'Completed','cancelled':'Cancelled'},
                'inspection_type':{'routine':'Routine','move_in':'Move-in','move_out':'Move-out','follow_up':'Follow-up','other':'Other'},
                'asset_status':{'in_service':'In service','stored':'Stored','needs_repair':'Needs repair','retired':'Retired'}},
            'outstanding_balances':{'title':'Outstanding balances','help':'Rent balances as of today using current entry statuses and allocations. Unallocated rent credit is shown separately and deducted from net rent due; refundable deposits and unapplied advance rent are not treated as rent payments. Future charges are separate. This is a rent-only view, not a complete statement of every tenant fee.','property':'Property / unit','lease':'Lease','due':'Unpaid rent due','overdue':'Overdue rent before unallocated credit','credit':'Unallocated rent credit','net':'Net rent due','future':'Future unpaid charges','empty':'No rent balances found.','as_of':'As of','review':'Review ledger','search':'Search','clear':'Clear','all':'All properties'}
        }
        for form,content in groups.items():
            rows=content if form=='property_registers' else {'ui':content}
            for key,options in rows.items():
                row,created=FormFieldSetting.objects.get_or_create(form_key=form,field_key=key,defaults={'label':key.replace('_',' ').title(),'option_labels':options})
                if not created:
                    merged=dict(row.option_labels or {})
                    for k,v in options.items():merged.setdefault(k,v)
                    if merged!=row.option_labels:row.option_labels=merged;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Portal navigation and register wording initialized. Existing records preserved.'))
