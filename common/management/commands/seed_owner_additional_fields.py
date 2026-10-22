from django.core.management.base import BaseCommand
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = "Initialize optional owner contact and property ownership field settings."

    def handle(self, *args, **options):
        profile = {
            "preferred_contact_method": ("Preferred Contact Method", "", {"":"No preference", "email":"Email", "phone":"Phone call", "text":"Text message"}),
            "alternate_contact_name": ("Alternate Contact Name", "A backup contact; this does not grant authority to approve work or receive money.", {}),
            "alternate_contact_email": ("Alternate Contact Email", "", {}),
            "alternate_contact_phone": ("Alternate Contact Phone", "", {}),
            "representative_name": ("Authorized Representative Name", "Record the company representative. Authority must be established separately.", {}),
            "representative_role": ("Representative Role / Title", "", {}),
            "representative_email": ("Representative Email", "", {}),
            "representative_phone": ("Representative Phone", "", {}),
        }
        ownership = {
            "statement_recipient_name": ("Statement Recipient Name", "Recipient designated for this property's owner statements; saving does not send a statement.", {}),
            "statement_recipient_email": ("Statement Recipient Email", "", {}),
            "maintenance_approval_limit": ("Maintenance Approval Limit ($)", "Blank means no limit has been specified. Zero means every expense requires owner approval. This records the instruction; it does not change maintenance approval workflows.", {}),
            "distribution_instructions": ("Distribution Instructions", "Record payment preferences or a reference to an approved payment setup. Do not enter bank account numbers here. Saving does not initiate a payment.", {}),
        }
        for form_key, fields in [("owner_profile", profile), ("property_ownership", ownership)]:
            for key, (label, help_text, choices) in fields.items():
                FormFieldSetting.objects.get_or_create(form_key=form_key, field_key=key,
                    defaults={"label":label, "help_text":help_text, "option_labels":choices})
        self.stdout.write(self.style.SUCCESS("Optional owner details initialized; existing edits preserved."))
