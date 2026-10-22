from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = 'Add overview subsections and editable document-delete wording.'

    @transaction.atomic
    def handle(self, *args, **options):
        groups = {
            'parties': ('Parties & Occupants', 'status landlords authorized_landlord_representative registered_tenants latest_named_tenants registered_occupants occupants_and_ages'),
            'term': ('Term & Renewal', 'start_date end_date move_in_date move_out_date signed_date primary_term_notice_days automatic_renewal_terms'),
            'payments': ('Rent & Payment', 'monthly_rent rent_due_day payment_methods payment_payee payment_address late_charge_starts_on_day initial_late_charge_amount daily_late_charge_amount returned_payment_charge'),
            'deposit': ('Security Deposit', 'security_deposit'),
            'pets': ('Pets & Animal Agreement', 'pet_authorization pet_name pet_type pet_breed pet_color pet_weight pet_age pet_gender pet_neutered_status pet_declawed_status pet_rabies_shots_current non_refundable_pet_fee_amount pet_deposit_amount pet_adjusted_monthly_rent'),
            'utilities': ('Utilities, Occupancy & Parking', 'tenant_paid_utilities landlord_paid_utilities maximum_vehicles guest_stay_limit_days'),
            'access': ('Access & Security', 'keybox_period_before_expiry_days keys_and_access_devices denied_access_trip_charge'),
            'maintenance': ('Maintenance Responsibilities', 'yard_maintenance_responsible_party yard_maintenance_contractor pool_and_spa_maintenance emergency_repair_contact condition_report_received_date'),
            'insurance': ('Insurance', 'renters_insurance_requirement insurance_proof_received_date'),
            'contact': ('Designated Contact', 'designated_contact_name designated_contact_phone designated_contact_email designated_contact_details'),
            'documents': ('Documents & Amendments', 'included_addenda_and_exhibits other_paragraphs'),
            'additional': ('Additional Information', ''),
        }
        for key, (label, fields) in groups.items():
            FormFieldSetting.objects.get_or_create(form_key='lease_summary',field_key='group-'+key,defaults={'label':label})
            for field_key in fields.split():
                item = FormFieldSetting.objects.filter(form_key='lease_summary',field_key=field_key).first()
                if item and 'subsection' not in item.option_labels:
                    item.option_labels = {**item.option_labels,'subsection':key}
                    item.save(update_fields=['option_labels'])
        document_type = FormFieldSetting.objects.get(form_key='lease_document',field_key='category')
        document_type.option_labels = {**document_type.option_labels, 'extension':'Lease Extensions'}
        document_type.save(update_fields=['option_labels'])
        item = FormFieldSetting.objects.get(form_key='lease_summary',field_key='other_paragraphs')
        item.help_text = 'Populated paragraph references from applicable executed continuations. Exact wording is retained here and in the signed documents; charges and tenant releases are not inferred.'
        item.save(update_fields=['help_text'])
        labels = {'delete':'Delete', 'confirm_delete':'Delete this COL360 document entry? The original file will remain in Google Drive or private storage.',
                  'deleting':'Deleting…', 'deleted':'Document entry deleted.', 'delete_failed':'Could not delete this document entry. Please try again.',
                  'session_expired':'Your session has expired. Sign in again.'}
        for key,label in labels.items():
            FormFieldSetting.objects.get_or_create(form_key='lease_document_ui',field_key=key,defaults={'label':label})
        self.stdout.write(self.style.SUCCESS('Overview subsections and document actions initialized.'))
